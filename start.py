from collections import deque
import math
import port_class
from port_class import (
    Port, Initiator, Target, Switch,
    register_port, connect_ports, disconnect_ports,
    initiator_index, target_index, switch_index
)

from node_class import TargetNode, SwitchNode, InitiatorNode

# Global dictionaries to store WWPN -> Port object mapping
target_ports = {}
host_ports = {}
switch_ports = {}
zoning_info = {}
all_zones = []

# Global dictionaries to node objects info
# here info is mapped by host_name for initiators, node_name for targets, and switch_name for switches
target_nodes = {}
switch_nodes = {}
initiator_nodes = {}

def parse_showport_output(file_path="output_isl_test_2.txt"):
    """
    Parse the showport, showhost, showportdev, and zoning output from the file and create Port objects.
    
    Args:
        file_path (str): Path to the output file
    
    Returns:
        list: List of created Port objects
    """
    global target_ports, host_ports, switch_ports, zoning_info, all_zones
    ports = []
    
    # Clear global all_zones for fresh parsing
    all_zones = []
    
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        # Find the showport, showhost, showportdev, and zoning output sections
        in_showport_section = False
        in_showhost_section = False
        in_showportdev_section = False
        in_zoning_section = False
        current_zone = []
        all_zones = []
        
        for line in lines:
            line = line.strip()
            
            # Start reading after "showport output:"
            if "showport output:" in line:
                in_showport_section = True
                in_showhost_section = False
                in_showportdev_section = False
                in_zoning_section = False
                continue
            
            # Start reading after "showhost output:"
            if "showhost output:" in line:
                in_showport_section = False
                in_showhost_section = True
                in_showportdev_section = False
                in_zoning_section = False
                continue
            
            # Start reading after "showportdev fcfabric"
            if "showportdev fcfabric" in line and "grep \"Online\"" in line:
                in_showport_section = False
                in_showhost_section = False
                in_showportdev_section = True
                in_zoning_section = False
                continue
            
            # Start reading after "zoning info:"
            if "zoning info:" in line:
                in_showport_section = False
                in_showhost_section = False
                in_showportdev_section = False
                in_zoning_section = True
                continue
            
            # Stop when we hit another section
            if in_showhost_section and "showportdev" in line:
                in_showhost_section = False
                continue
            
            if in_showportdev_section and "zoning info:" in line:
                in_showportdev_section = False
                continue
            
            # Parse the showport lines
            if in_showport_section and "|" in line:
                # Split by | and clean up whitespace
                parts = [part.strip() for part in line.split("|")]
                
                if len(parts) >= 5:
                    port_id = parts[0]          # First column: NSP
                    port_type = parts[1]        # Second column: port type
                    wwnn = parts[3]             # Fourth column: WWNN  
                    wwpn = parts[4]             # Fifth column: WWPN
                    
                    # Create appropriate port object based on type
                    if port_type.lower() == "target":
                        # Extract the first value from port_id (e.g., "0" from "0:3:1")
                        node_number = port_id.split(':')[0] if ':' in port_id else port_id
                        port = Target(
                            wwpn=wwpn,
                            port_id=port_id,
                            wwnn=wwnn,
                            speed="32Gbps",  # Default speed
                            array_name=f"node_{node_number}"
                        )
                    elif port_type.lower() == "initiator":
                        port = Initiator(
                            wwpn=wwpn,
                            port_id=port_id,
                            wwnn=wwnn,
                            speed="32Gbps",  # Default speed
                            host_name=f"Host_{port_id.replace(':', '_')}"
                        )
                    else:  # Default to generic Port for other types
                        port = Port(
                            wwpn=wwpn,
                            port_id=port_id,
                            wwnn=wwnn,
                            port_type=port_type,
                            speed="32Gbps"
                        )
                    
                    ports.append(port)
                    target_ports[wwpn] = port  # Add to global dictionary with WWPN as key
                    register_port(port)
                    print(f"Created {port_type} port: NSP={port_id}, WWPN={wwpn}")
            
            # Parse the showhost lines
            if in_showhost_section and line and not line.startswith("showhost"):
                wwpn = line.strip()
                if wwpn:  # Make sure it's not an empty line
                    # Create an Initiator port for host WWPNs
                    port = Initiator(
                        wwpn=wwpn,
                        port_id="N/A",  # NSP not available in showhost output
                        wwnn="N/A",  # WWNN not available in showhost output
                        speed="32Gbps",  # Default speed
                        host_name=f"Host_{wwpn[-8:]}"  # Use last 8 chars of WWPN for host name
                    )
                    
                    ports.append(port)
                    host_ports[wwpn] = port  # Add to host_ports dictionary
                    register_port(port)
                    print(f"Created host initiator port: WWPN={wwpn}")
            
            # Parse the showportdev lines
            if in_showportdev_section and "|" in line:
                # Split by | and clean up whitespace
                parts = [part.strip() for part in line.split("|")]
                
                if len(parts) >= 6:
                    port_index = parts[0]           # First column: port index
                    switch_wwpn = parts[1]          # Second column: switch WWPN
                    switch_port_type = parts[2]     # Third column: port type (F-Port, E-Port, etc.)
                    speed = parts[4]                # Fifth column: speed
                    connection = parts[5]
                    
                    # Create Switch port object
                    switch_port = Switch(
                        wwpn=switch_wwpn,
                        port_id=port_index,
                        wwnn="N/A",  # WWNN not available in showportdev output
                        speed=speed,
                        connection=connection,  # Connected port WWPN
                        switch_name=f"Switch_{switch_wwpn[-8:]}",  # Use last 8 chars of WWPN
                        port_index=port_index
                    )
                    
                    ports.append(switch_port)
                    switch_ports[switch_wwpn] = switch_port  # Add to switch_ports dictionary
                    register_port(switch_port)
                    print(f"Created switch port: Port={port_index}, WWPN={switch_wwpn}, Type={switch_port_type}")
            
            # Parse the zoning info
            if in_zoning_section:
                if line.startswith("zone"):
                    # If we have a previous zone, process it
                    if current_zone:
                        all_zones.append(current_zone.copy())
                        print(f"Processed zone with WWPNs: {current_zone}")
                    
                    # Start a new zone
                    current_zone = []
                elif line and not line.startswith("zone") and not line.startswith("Node information"):
                    # This is a WWPN in the current zone
                    wwpn = line.strip()
                    if wwpn and not any(keyword in wwpn.lower() for keyword in ['node information', 'host_info', 'switch info']):
                        current_zone.append(wwpn)
                        print(f"Added WWPN {wwpn} to current zone")
                
                # Stop processing zoning when we hit the next section
                if line.startswith("Node information"):
                    # Process the final zone before stopping
                    if current_zone:
                        all_zones.append(current_zone.copy())
                        print(f"Processed final zone with WWPNs: {current_zone}")
                        current_zone = []
                    in_zoning_section = False
                    continue
        
        # Process the last zone if it exists
        if current_zone:
            all_zones.append(current_zone.copy())
            print(f"Processed final zone with WWPNs: {current_zone}")
    
        # Now create the zoning_info mapping - each WWPN maps to its zone
        # But we need to handle the fact that a WWPN can appear in multiple zones
        # For the ISL analysis, we'll use all_zones directly
        for i, zone in enumerate(all_zones):
            for wwpn in zone:
                zoning_info[wwpn] = zone  # This will overwrite, but that's ok for now
                # We'll use all_zones for proper zone analysis
    
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
    except Exception as e:
        print(f"Error parsing file: {e}")
    
    return ports

def parse_node_information(file_path="output_isl_test.txt"):
    """
    Parse the Node information variables, host_info, and Switch info sections 
    and create TargetNode, InitiatorNode, and SwitchNode objects.
    
    Args:
        file_path (str): Path to the output file
    """
    global target_nodes, initiator_nodes, switch_nodes
    
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        node_count = None
        node_version = None
        host_info = None
        switch_name = None
        switch_logical_name = None
        switch_vendor = None
        switch_model = None
        switch_release = None
        
        # Find the Node information variables section
        in_node_info_section = False
        in_host_info_section = False
        in_switch_info_section = False
        
        for line in lines:
            line = line.strip()
            
            # Start reading after "Node information variables:"
            if "Node information variables:" in line:
                in_node_info_section = True
                in_host_info_section = False
                in_switch_info_section = False
                print(f"Found Node information variables section")
                continue
            
            # Start reading after "host_info"
            if line.startswith("host_info"):
                in_node_info_section = False
                in_host_info_section = True
                in_switch_info_section = False
                print(f"Found host_info section")
                # Parse the host_info line directly
                if "=" in line:
                    _, value = line.split("=", 1)
                    host_info = value.strip()
                    print(f"Found host_info: {host_info}")
                continue
            
            # Start reading after "Switch info:"
            if "Switch info:" in line:
                in_node_info_section = False
                in_host_info_section = False
                in_switch_info_section = True
                print(f"Found Switch info section")
                continue
            
            # Parse lines in the node info section
            if in_node_info_section:
                print(f"Processing node info line: '{line}'")
                
                # Check for the end of the section
                if line.startswith("host_info") or line.startswith("Switch info") or not line:
                    print("Reached end of node info section")
                    continue
                
                # Parse key=value pairs
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    print(f"Found key-value pair: {key} = {value}")
                    
                    if key == "node_count":
                        node_count = int(value)
                        print(f"Set node_count to: {node_count}")
                    elif key == "node_version":
                        node_version = value
                        print(f"Set node_version to: {node_version}")
            
            # Parse lines in the switch info section
            if in_switch_info_section:
                print(f"Processing switch info line: '{line}'")
                
                # Parse key=value pairs
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    print(f"Found switch key-value pair: {key} = {value}")
                    
                    if key == "switch_name":
                        switch_name = value
                        print(f"Set switch_name to: {switch_name}")
                    elif key == "switch_logical_name":
                        switch_logical_name = value
                        print(f"Set switch_logical_name to: {switch_logical_name}")
                    elif key == "switch_vendor":
                        switch_vendor = value
                        print(f"Set switch_vendor to: {switch_vendor}")
                    elif key == "switch_model":
                        switch_model = value
                        print(f"Set switch_model to: {switch_model}")
                    elif key == "switch_release":
                        switch_release = value
                        print(f"Set switch_release to: {switch_release}")
        
        # Create TargetNode objects based on node_count
        if node_count is not None and node_version is not None:
            print(f"\n=== Creating Target Nodes ===")
            print(f"Node count: {node_count}, Node version: {node_version}")
            
            for i in range(node_count):
                node_name = f"node_{i}"
                target_node = TargetNode(
                    name=node_name,
                    sw_version=node_version
                )
                
                target_nodes[node_name] = target_node
                print(f"Created TargetNode: {node_name} with sw_version={node_version}")
        else:
            print(f"Warning: Could not find node_count ({node_count}) or node_version ({node_version}) in the file")
        
        # Create InitiatorNode object based on host_info
        if host_info:
            print(f"\n=== Creating Initiator Node ===")
            print(f"Host info: {host_info}")
            
            # Parse host_info to extract HBA and firmware version
            # Format: SN1610Q FW:v9.12.01 DVR:v10.02.10.00-k1-debug
            hba = None
            fw_version = None
            
            parts = host_info.split()
            if len(parts) >= 2:
                hba = parts[0]  # SN1610Q
                for part in parts[1:]:
                    if part.startswith("FW:"):
                        fw_version = part[3:]  # v9.12.01
                        break
            
            initiator_node = InitiatorNode(
                name="host_1",  # Default name
                hba=hba,
                fw_version=fw_version
            )
            
            initiator_nodes["host_1"] = initiator_node
            print(f"Created InitiatorNode: host_1 with hba={hba}, fw_version={fw_version}")
        else:
            print("Warning: Could not find host_info in the file")
        
        # Create SwitchNode object based on switch info
        if switch_name and switch_vendor and switch_model and switch_release:
            print(f"\n=== Creating Switch Node ===")
            print(f"Switch name: {switch_name}")
            print(f"Switch vendor: {switch_vendor}")
            print(f"Switch model: {switch_model}")
            print(f"Switch release: {switch_release}")
            
            switch_node = SwitchNode(
                name=switch_logical_name or "switch_1",  # Use logical name if available, otherwise default
                wwnn=switch_name,  # Use switch_name as WWNN
                release_version=switch_release,
                model=switch_model,
                port_count=None,  # Not available in current data
                vendor=switch_vendor
            )
            
            node_key = switch_logical_name or "switch_1"
            switch_nodes[node_key] = switch_node
            print(f"Created SwitchNode: {node_key} with model={switch_model}, vendor={switch_vendor}")
        else:
            print(f"Warning: Could not find complete switch info in the file")
            print(f"switch_name: {switch_name}, vendor: {switch_vendor}, model: {switch_model}, release: {switch_release}")
    
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
    except Exception as e:
        print(f"Error parsing node information: {e}")

def establish_switch_connections():
    """
    Iterate through switch_ports and establish bidirectional connections
    with target_ports and host_ports based on the connection field.
    """
    global switch_ports, target_ports, host_ports
    
    print("\n=== Establishing Switch Connections ===")
    
    for switch_wwpn, switch_port in switch_ports.items():
        # Get the connected port WWPN from the switch's connection field
        connected_wwpn = switch_port.connection
        
        if connected_wwpn:
            # Search for the connected port in target_ports
            if connected_wwpn in target_ports:
                target_port = target_ports[connected_wwpn]
                if target_port.connection is None:
                    target_port.connection = switch_wwpn
                    print(f"Connected switch {switch_wwpn} to target {connected_wwpn}")
                else:
                    print(f"Target {connected_wwpn} already connected to {target_port.connection}")
            
            # Search for the connected port in host_ports
            elif connected_wwpn in host_ports:
                host_port = host_ports[connected_wwpn]
                if host_port.connection is None:
                    host_port.connection = switch_wwpn
                    print(f"Connected switch {switch_wwpn} to host {connected_wwpn}")
                else:
                    print(f"Host {connected_wwpn} already connected to {host_port.connection}")
            
            # Search for the connected port in switch_ports (for switch-to-switch connections)
            elif connected_wwpn in switch_ports:
                other_switch_port = switch_ports[connected_wwpn]
                if other_switch_port.connection is None:
                    other_switch_port.connection = switch_wwpn
                    print(f"Connected switch {switch_wwpn} to switch {connected_wwpn}")
                else:
                    print(f"Switch {connected_wwpn} already connected to {other_switch_port.connection}")
            
            else:
                print(f"Warning: Connected port {connected_wwpn} not found in any port dictionary")
        else:
            print(f"Switch {switch_wwpn} has no connection information")

def debug_zoning_info():
    """Debug function to show zoning info details."""
    global all_zones
    print("\n=== ZONING INFO DEBUG ===")
    print(f"Total entries in zoning_info: {len(zoning_info)}")
    print(f"Total zones parsed: {len(all_zones)}")
    
    # Show all zones from the properly parsed all_zones list
    for i, zone_members in enumerate(all_zones, 1):
        print(f"\nZone {i}:")
        print(f"  Members: {zone_members}")
        
        # Show which WWPNs in this zone are also keys in zoning_info
        zone_wwpns_in_dict = []
        for wwpn in zone_members:
            if wwpn in zoning_info:
                zone_wwpns_in_dict.append(wwpn)
        print(f"  WWPNs that map to this zone in zoning_info: {zone_wwpns_in_dict}")
    
    # Group by zone content to show unique zones from zoning_info (for comparison)
    zones_from_dict = {}
    for wwpn, zone_members in zoning_info.items():
        zone_key = tuple(sorted(zone_members))  # Use sorted tuple as key
        if zone_key not in zones_from_dict:
            zones_from_dict[zone_key] = []
        zones_from_dict[zone_key].append(wwpn)
    
    print(f"\nNumber of unique zones from zoning_info dict: {len(zones_from_dict)}")
    
    print("\n=== INDIVIDUAL ENTRIES (zoning_info dict) ===")
    for wwpn, zone_members in zoning_info.items():
        print(f"WWPN: {wwpn} -> Zone: {zone_members}")

def interactive_check_connectivity():
    """Interactive connectivity check."""
    print("\nCHECK FABRIC CONNECTIVITY")
    print("-" * 35)
    
    # Show endpoints only (initiators and targets)
    print("Available endpoints:")
    
    if initiator_index:
        print("\nInitiators:")
        for wwpn, initiator in initiator_index.items():
            print(f"   {wwpn} ({initiator.host_name})")
    
    if target_index:
        print("\nTargets:")
        for wwpn, target in target_index.items():
            print(f"   {wwpn} ({target.array_name})")
    
    print("\n")
    source_wwpn = input("Enter source endpoint WWPN: ").strip()
    dest_wwpn = input("Enter destination endpoint WWPN: ").strip()
    
    if source_wwpn and dest_wwpn:
        check_fabric_connectivity(source_wwpn, dest_wwpn)
    else:
        print("Invalid input. Both WWPNs are required.")

def check_fabric_connectivity(source_wwpn, destination_wwpn):
    """
    Check if two endpoints can communicate through the fabric and display the path.
    
    Args:
        source_wwpn (str): WWPN of source endpoint
        destination_wwpn (str): WWPN of destination endpoint
    """
    print(f"\n=== Checking Connectivity: {source_wwpn} -> {destination_wwpn} ===")
    
    source_port = get_port_by_wwpn(source_wwpn)
    dest_port = get_port_by_wwpn(destination_wwpn)
    
    if not source_port or not dest_port:
        print("ERROR: One or both ports not found")
        return False
    
    # Display port information
    source_type = "Initiator" if isinstance(source_port, Initiator) else "Target" if isinstance(source_port, Target) else "Switch"
    dest_type = "Initiator" if isinstance(dest_port, Initiator) else "Target" if isinstance(dest_port, Target) else "Switch"
    
    source_name = getattr(source_port, 'host_name', None) or getattr(source_port, 'array_name', None) or getattr(source_port, 'switch_name', 'Unknown')
    dest_name = getattr(dest_port, 'host_name', None) or getattr(dest_port, 'array_name', None) or getattr(dest_port, 'switch_name', 'Unknown')
    
    print(f"Source: {source_type} ({source_name}) - {source_wwpn}")
    print(f"Destination: {dest_type} ({dest_name}) - {destination_wwpn}")
    
    # Print direct connection information
    print(f"Source port connected to: {source_port.connection}")
    print(f"Destination port connected to: {dest_port.connection}")
    
    # Find path
    path = find_path_between_endpoints(source_wwpn, destination_wwpn)
    
    if path:
        print("SUCCESS: Path found!")
        print("Path details:")
        
        for i, wwpn in enumerate(path):
            port = get_port_by_wwpn(wwpn)
            port_info = ""
            
            if isinstance(port, Initiator):
                port_info = f"Initiator ({port.host_name})"
            elif isinstance(port, Target):
                port_info = f"Target ({port.array_name})"
            elif isinstance(port, Switch):
                port_info = f"Switch ({port.switch_name}:{port.port_index})"
                if hasattr(port, 'switch_port_type') and port.switch_port_type:
                    port_info += f" [{port.switch_port_type.upper()}]"
            
            # Add speed information
            port_info += f" - {port.speed}"
            
            if i < len(path) - 1:
                next_port = get_port_by_wwpn(path[i+1])
                
                # Show speed connection info without warnings
                speed_info = f" ({port.speed} → {next_port.speed})"
                    
                print(f"  {i+1}. {wwpn} - {port_info} connected to {next_port.wwpn}{speed_info}")
                print(f"     |")
            else:
                print(f"  {i+1}. {wwpn} - {port_info}")
        
        # Add path speed analysis
        print("\nPath speed analysis:")
        speeds = {}
        min_speed = None
        min_speed_segment = None
        
        # Find all speeds in the path and the lowest speed
        for i in range(len(path)-1):
            port1 = get_port_by_wwpn(path[i])
            port2 = get_port_by_wwpn(path[i+1])
            
            # Extract numeric part from speed (e.g., "16Gb" -> 16)
            speed1_value = int(''.join(filter(str.isdigit, port1.speed)))
            speed2_value = int(''.join(filter(str.isdigit, port2.speed)))
            
            # The effective speed of a connection is the minimum of the two ports
            segment_speed = min(speed1_value, speed2_value)
            segment = f"{port1.wwpn} → {port2.wwpn}"
            
            if segment_speed not in speeds:
                speeds[segment_speed] = []
            speeds[segment_speed].append(segment)
            
            if min_speed is None or segment_speed < min_speed:
                min_speed = segment_speed
                min_speed_segment = segment
        
        # Report speed information
        if speeds:
            print(f"  Path contains links with the following speeds: {', '.join([f'{s}Gb' for s in sorted(speeds.keys())])}")
            print(f"  Effective path speed: {min_speed}Gb (determined by the slowest link)")
            
            if len(speeds) > 1:
                print("  Speed limited by:")
                for segment in speeds[min_speed]:
                    port1_wwpn, port2_wwpn = segment.split(" → ")
                    port1 = get_port_by_wwpn(port1_wwpn)
                    port2 = get_port_by_wwpn(port2_wwpn)
                    port1_info = f"{port1.__class__.__name__} {getattr(port1, 'host_name', getattr(port1, 'array_name', getattr(port1, 'switch_name', '')))}"
                    port2_info = f"{port2.__class__.__name__} {getattr(port2, 'host_name', getattr(port2, 'array_name', getattr(port2, 'switch_name', '')))}"
                    print(f"    - {port1_info} → {port2_info}: {min_speed}Gb")
        
        return True
    else:
        print("ERROR: No path found - devices cannot communicate through current fabric topology")
        print("\nDEBUG: Let's analyze the connections...")
        
        # Print all connections for debugging
        print("\nCurrent connections:")
        for index_dict, type_name in [(initiator_index, "Initiators"), (switch_index, "Switches"), (target_index, "Targets")]:
            print(f"\n{type_name}:")
            for wwpn, port in index_dict.items():
                conn_port = get_port_by_wwpn(port.connection) if port.is_connected() else None
                if port.is_connected():
                    conn_type = conn_port.__class__.__name__ if conn_port else "Unknown"
                    conn_info = f"-> {port.connection} ({conn_type})"
                else:
                    conn_info = "Not connected"
                print(f"  {wwpn}: {conn_info}")
        
        return False

def find_path_between_endpoints(source_wwpn, destination_wwpn):
    """
    Find a traversable path between two endpoints (initiator/target) through the fabric.
    
    Args:
        source_wwpn (str): WWPN of source endpoint (initiator or target)
        destination_wwpn (str): WWPN of destination endpoint (target or initiator)
    
    Returns:
        list: Path as list of WWPNs from source to destination, or None if no path exists
    """
    source_port = get_port_by_wwpn(source_wwpn)
    dest_port = get_port_by_wwpn(destination_wwpn)
    
    if not source_port or not dest_port:
        print(f"Error: Could not find source ({source_wwpn}) or destination ({destination_wwpn}) port")
        return None
    
    # Check if both are endpoints (initiator or target)
    if not (isinstance(source_port, (Initiator, Target)) and isinstance(dest_port, (Initiator, Target))):
        print(f"Error: Both source and destination must be initiators or targets")
        return None
    
    # Build adjacency list from current connections
    adjacency = {}
    
    # Group switch ports by their actual switch identity (not WWNN)
    # We need to identify which ports belong to the same physical switch
    switch_groups = {}
    
    for wwpn, switch_port in switch_index.items():
        # Use the base part of the WWPN to identify the switch
        # For example: 10000000AAAA0001, 10000000AAAA0002, 10000000AAAA000A all belong to switch AAAA
        switch_base = switch_port.wwpn[:12]  # Take first 12 characters
        if switch_base not in switch_groups:
            switch_groups[switch_base] = []
        switch_groups[switch_base].append(wwpn)
    
    # Add only direct physical connections to adjacency list (both directions)
    for index_dict in [initiator_index, target_index, switch_index]:
        for wwpn, port in index_dict.items():
            if port.is_connected():
                # Initialize the adjacency list entry if it doesn't exist
                if wwpn not in adjacency:
                    adjacency[wwpn] = []
                
                # Get the port this port is connected to
                connected_port = get_port_by_wwpn(port.connection)
                if not connected_port:
                    print(f"WARNING: Port {wwpn} is connected to non-existent port {port.connection}")
                    continue
                    
                # Add the connection to the adjacency list
                if port.connection not in adjacency[wwpn]:
                    adjacency[wwpn].append(port.connection)
                
                # Add the reverse connection too
                if port.connection not in adjacency:
                    adjacency[port.connection] = []
                
                if wwpn not in adjacency[port.connection]:
                    adjacency[port.connection].append(wwpn)
    
    # Now add internal switch connections, but only between F-ports and E-ports
    # This models how traffic can enter through F-port and exit through E-port (or vice versa)
    for switch_base, ports in switch_groups.items():
        f_ports = []  # Ports connected to devices (F-ports)
        e_ports = []  # Ports connected to other switches (E-ports)
        
        for port_wwpn in ports:
            switch_port = switch_index[port_wwpn]
            if switch_port.is_connected():
                connected_port = get_port_by_wwpn(switch_port.connection)
                if connected_port:
                    if isinstance(connected_port, (Initiator, Target)):
                        f_ports.append(port_wwpn)  # This is an F-port
                    elif isinstance(connected_port, Switch):
                        e_ports.append(port_wwpn)  # This is an E-port (ISL)
        
        # Connect F-ports to E-ports (allowing traffic to flow through the switch)
        for f_port in f_ports:
            for e_port in e_ports:
                # Add connection from F-port to E-port
                if f_port not in adjacency:
                    adjacency[f_port] = []
                if e_port not in adjacency[f_port]:
                    adjacency[f_port].append(e_port)
                
                # Add connection from E-port to F-port
                if e_port not in adjacency:
                    adjacency[e_port] = []
                if f_port not in adjacency[e_port]:
                    adjacency[e_port].append(f_port)
    
    # Print adjacency list for debugging
    # print("\nDEBUG: Adjacency List (including internal switch connections)")
    # for port, connections in adjacency.items():
    #     port_obj = get_port_by_wwpn(port)
    #     port_type = "Unknown"
    #     port_info = ""
    #     if not port_obj:
    #         print(f"WARNING: Port {port} in adjacency list but not found in indices!")
    #     else:
    #         if isinstance(port_obj, Initiator): 
    #             port_type = "Initiator"
    #             port_info = f"({port_obj.host_name})"
    #         elif isinstance(port_obj, Target): 
    #             port_type = "Target"
    #             port_info = f"({port_obj.array_name})"
    #         elif isinstance(port_obj, Switch): 
    #             port_type = "Switch"
    #             port_info = f"({port_obj.switch_name}:{port_obj.port_index})"
        
    #     print(f"{port} ({port_type}{' ' + port_info if port_info else ''}) -> {connections}")
    
    # Use BFS to find shortest path through the fabric
    queue = deque([(source_wwpn, [source_wwpn])])
    visited = set([source_wwpn])
    
    while queue:
        current_wwpn, path = queue.popleft()
        
        # We reached our destination
        if current_wwpn == destination_wwpn:
            return path
        
        # Explore all neighbors
        if current_wwpn in adjacency:
            for neighbor_wwpn in adjacency[current_wwpn]:
                if neighbor_wwpn not in visited:
                    visited.add(neighbor_wwpn)
                    new_path = path + [neighbor_wwpn]
                    queue.append((neighbor_wwpn, new_path))
    
    # No path found
    print("\nDEBUG: BFS search completed with no path found")
    print(f"Starting from {source_wwpn}, visited {len(visited)} ports:")
    print(f"Visited ports: {list(visited)}")
    return None

def show_all_connections():
    """Display all current connections in the SAN."""
    print("\n=== Current SAN Connections ===")
    
    print("Initiators:")
    for wwpn, initiator in host_ports.items():
        connection_status = f"-> {initiator.connection}" if initiator.is_connected() else "Not connected"
        print(f"  {wwpn} ({initiator.host_name}): {connection_status}")
    
    print("Targets:")
    for wwpn, target in target_ports.items():
        connection_status = f"-> {target.connection}" if target.is_connected() else "Not connected"
        print(f"  {wwpn} ({target.array_name}): {connection_status}")
    
    print("Switches:")
    for wwpn, switch in switch_ports.items():
        connection_status = f"-> {switch.connection}" if switch.is_connected() else "Not connected"
        print(f"  {wwpn} ({switch.switch_name}:{switch.port_index}): {connection_status}")

def get_port_by_wwpn(wwpn):
    """Get a port object by its WWPN."""
    if wwpn in host_ports:
        return host_ports[wwpn]
    elif wwpn in target_ports:
        return target_ports[wwpn]
    elif wwpn in switch_ports:
        return switch_ports[wwpn]
    return None

def check_isl_oversubscription():
    """
    Analyzes ISL oversubscription based on zoning information.
    Traverses paths for all zone members and checks if ISL bandwidth is at least 1/4th of potential traffic.
    Returns information about oversubscribed ISLs.
    """
    import math
    
    # Dictionary to track traffic per target node: {node_id: traffic}
    node_traffic = {}
    
    # Dictionary to track links per target node: {node_id: {link_speed: count}}
    node_links = {}
    
    # Dictionary to store node details
    node_details = {}
    
    # Analyze target ports to identify nodes and their connections
    for wwpn, target_port in target_ports.items():
        if isinstance(target_port, Target):
            # Extract node number from NSP (e.g., "0:4:1" -> node 0)
            node_id = target_port.port_id.split(':')[0] if ':' in target_port.port_id else target_port.port_id
            
            # Initialize node tracking
            if node_id not in node_traffic:
                node_traffic[node_id] = 0
                node_links[node_id] = {}
                node_details[node_id] = {
                    "ports": [],
                    "array_name": target_port.array_name
                }
            
            # Add this port to the node
            node_details[node_id]["ports"].append({
                "wwpn": wwpn,
                "port_id": target_port.port_id,
                "speed": target_port.speed
            })
            
            # Track the link speed for this node
            speed_value = int(''.join(filter(str.isdigit, target_port.speed)))
            if speed_value not in node_links[node_id]:
                node_links[node_id][speed_value] = 0
            node_links[node_id][speed_value] += 1
    
    if not node_traffic:
        return {"status": "No target nodes found", "oversubscribed_nodes": []}
    
    # Extract unique zones from all_zones directly
    global all_zones
    zones = all_zones  # Use the correctly parsed zones directly
    
    # Process each zone to calculate traffic
    for zone_members in zones:
        # Identify all initiators and targets in this zone
        initiators = []
        targets = []
        
        for wwpn in zone_members:
            port = get_port_by_wwpn(wwpn)
            if not port:
                continue
                
            if isinstance(port, Initiator):
                initiators.append(port)
            elif isinstance(port, Target):
                targets.append(port)
        
        # For each initiator-target pair in the zone
        for initiator in initiators:
            init_speed = int(''.join(filter(str.isdigit, initiator.speed)))
            
            for target in targets:
                # Get the node ID for this target
                target_node_id = target.port_id.split(':')[0] if ':' in target.port_id else target.port_id
                
                # Extract speed values
                target_speed = int(''.join(filter(str.isdigit, target.speed)))
                
                # Traffic is limited by the slower of the two endpoints
                connection_speed = min(init_speed, target_speed)
                
                # Add traffic to the target node
                node_traffic[target_node_id] += connection_speed
    
    # Check for oversubscription per node
    oversubscription_threshold = 4  # 4:1 ratio threshold (industry standard)
    oversubscribed_nodes = []
    
    for node_id, traffic in node_traffic.items():
        if traffic == 0:
            continue
        
        # Calculate total link capacity for this node
        total_link_capacity = 0
        for speed, count in node_links[node_id].items():
            total_link_capacity += speed * count
        
        if total_link_capacity == 0:
            continue
            
        # Calculate oversubscription ratio
        ratio = traffic / total_link_capacity if total_link_capacity > 0 else float('inf')
        
        # Check if oversubscribed
        if ratio > oversubscription_threshold:
            # Calculate additional links needed
            additional_links_needed = math.ceil(traffic / oversubscription_threshold) - total_link_capacity
            
            oversubscribed_nodes.append({
                "node_id": node_id,
                "array_name": node_details[node_id]["array_name"],
                "ports": node_details[node_id]["ports"],
                "total_link_capacity": total_link_capacity,
                "traffic": traffic,
                "ratio": ratio,
                "additional_capacity_needed": additional_links_needed,
                "link_details": node_links[node_id]
            })
    
    # If no traditional ISLs found but we have oversubscribed nodes, 
    # treat node links as potential bottlenecks
    if oversubscribed_nodes:
        return {
            "status": "Node link oversubscription detected",
            "total_nodes": len(node_traffic),
            "oversubscribed_nodes": oversubscribed_nodes,
            "zones_analyzed": len(zones)
        }
    
    # Also check for traditional ISLs between switches
    # Group ISLs by switch pairs to handle multiple ISLs between same switches
    switch_pair_isls = {}  # Track ISLs grouped by switch pairs
    isl_traffic = {}
    isl_details = {}
    
    # Find all switch-to-switch connections (ISLs) and group by switch pairs
    for wwpn, switch_port in switch_index.items():
        # Check if this port connects to another switch
        if switch_port.is_connected():
            connected_port = get_port_by_wwpn(switch_port.connection)
            if connected_port and isinstance(connected_port, Switch):
                
                # Identify the switch pair (sorted to ensure consistency)
                switch1_base = switch_port.wwpn[:12]  # e.g., "10000000AAAA"
                switch2_base = connected_port.wwpn[:12]  # e.g., "10000000BBBB"
                switch_pair = tuple(sorted([switch1_base, switch2_base]))
                
                # Initialize switch pair if not seen before
                if switch_pair not in switch_pair_isls:
                    switch_pair_isls[switch_pair] = {
                        "isls": [],
                        "total_capacity": 0,
                        "traffic": 0
                    }
                
                # Extract numeric speed value
                speed_value = int(''.join(filter(str.isdigit, switch_port.speed)))
                
                # Create a unique identifier for this bidirectional ISL
                isl_pair = tuple(sorted([wwpn, switch_port.connection]))
                
                # Check if we've already processed this ISL pair
                already_added = False
                for existing_isl in switch_pair_isls[switch_pair]["isls"]:
                    if existing_isl["isl_pair"] == isl_pair:
                        already_added = True
                        break
                
                if not already_added:
                    # Add this ISL to the switch pair
                    isl_info = {
                        "isl_pair": isl_pair,
                        "representative_wwpn": isl_pair[0],
                        "speed": speed_value,
                        "switch_name": switch_port.switch_name,
                        "port_index": switch_port.port_index,
                        "remote_wwpn": switch_port.connection
                    }
                    
                    switch_pair_isls[switch_pair]["isls"].append(isl_info)
                    switch_pair_isls[switch_pair]["total_capacity"] += speed_value
                    
                    # Initialize traffic counter for this ISL pair
                    isl_traffic[switch_pair] = 0
                    isl_details[switch_pair] = switch_pair_isls[switch_pair]
    
    if not isl_traffic:
        return {"status": "No traditional ISLs found - single switch fabric", "oversubscribed_isls": [], "total_nodes": len(node_traffic), "zones_analyzed": len(zones)}
    
    # Process zones for ISL traffic (traditional multi-switch analysis)
    for i, zone_members in enumerate(zones, 1):
        # Identify all initiators and targets in this zone
        initiators = []
        targets = []
        
        for wwpn in zone_members:
            port = get_port_by_wwpn(wwpn)
            if not port:
                continue
                
            if isinstance(port, Initiator):
                initiators.append(port)
            elif isinstance(port, Target):
                targets.append(port)
        
        # For each initiator-target pair in the zone
        for initiator in initiators:
            for target in targets:
                # Find path between initiator and target
                path = find_path_between_endpoints(initiator.wwpn, target.wwpn)
                
                if not path:
                    continue
                
                # Extract speed values
                init_speed = int(''.join(filter(str.isdigit, initiator.speed)))
                target_speed = int(''.join(filter(str.isdigit, target.speed)))
                
                # Traffic is limited by the slower of the two endpoints
                connection_speed = min(init_speed, target_speed)
                
                # For each port in the path, check if it's part of an ISL
                # Track which switch pairs we've already counted for this path to avoid double-counting
                counted_switch_pairs = set()
                
                for port_wwpn in path:
                    # Check if this port is part of any switch pair ISL
                    port_obj = get_port_by_wwpn(port_wwpn)
                    if port_obj and isinstance(port_obj, Switch):
                        switch_base = port_obj.wwpn[:12]
                        
                        # Find which switch pair this port belongs to
                        for switch_pair, pair_info in switch_pair_isls.items():
                            if switch_base in switch_pair and switch_pair not in counted_switch_pairs:
                                # Add traffic to this switch pair (only once per switch pair per path)
                                isl_traffic[switch_pair] += connection_speed
                                counted_switch_pairs.add(switch_pair)
                                break
    
    # Check for oversubscription on switch pair ISLs
    oversubscribed_isls = []
    
    for switch_pair, traffic in isl_traffic.items():
        if traffic == 0:
            continue
            
        pair_info = isl_details[switch_pair]
        total_isl_capacity = pair_info["total_capacity"]
        
        # Calculate oversubscription ratio
        ratio = traffic / total_isl_capacity if total_isl_capacity > 0 else float('inf')
        
        # Check if oversubscribed
        if ratio > oversubscription_threshold:
            # Calculate additional ISLs needed
            additional_capacity_needed = math.ceil(traffic / oversubscription_threshold) - total_isl_capacity
            
            # Get representative ISL info for display
            primary_isl = pair_info["isls"][0]  # Use first ISL as representative
            
            oversubscribed_isls.append({
                "switch_pair": switch_pair,
                "wwpn": primary_isl["representative_wwpn"],
                "switch_name": primary_isl["switch_name"],
                "port_index": primary_isl["port_index"],
                "total_capacity": total_isl_capacity,
                "individual_isl_speed": primary_isl["speed"],
                "num_isls": len(pair_info["isls"]),
                "traffic": traffic,
                "ratio": ratio,
                "additional_capacity_needed": additional_capacity_needed,
                "remote_wwpn": primary_isl["remote_wwpn"],
                "all_isls": pair_info["isls"]
            })
    
    # Return the analysis results
    return {
        "status": "Analysis complete",
        "total_isls": sum(len(pair_info["isls"]) for pair_info in switch_pair_isls.values()),
        "total_switch_pairs": len(switch_pair_isls),
        "oversubscribed_isls": oversubscribed_isls,
        "zones_analyzed": len(zones)
    }

def display_isl_oversubscription_analysis():
    """
    Runs ISL oversubscription check and displays formatted results.
    This function is for user-facing display purposes only.
    """
    import math
    
    print("\n=== ISL OVERSUBSCRIPTION ANALYSIS ===")
    
    # Run the analysis
    analysis = check_isl_oversubscription()
    
    print(f"Analysis Status: {analysis['status']}")
    
    if "zones_analyzed" in analysis:
        print(f"Analyzed {analysis['zones_analyzed']} unique zones.")
    
    # Handle node-based oversubscription
    if "oversubscribed_nodes" in analysis:
        if analysis["oversubscribed_nodes"]:
            print(f"\nDetected {len(analysis['oversubscribed_nodes'])} oversubscribed storage nodes:")
            
            for i, node in enumerate(analysis["oversubscribed_nodes"], 1):
                print(f"\n{i}. Storage Node {node['node_id']} ({node['array_name']}):")
                print(f"   - Oversubscription ratio: {node['ratio']:.2f}:1")
                print(f"   - Total link capacity: {node['total_link_capacity']}G")
                print(f"   - Cumulative traffic demand: {node['traffic']}G")
                print(f"   - Ports on this node: {len(node['ports'])}")
                
                for port in node['ports']:
                    print(f"     * {port['wwpn']} ({port['port_id']}) - {port['speed']}")
                
                print(f"   - Current link distribution: {dict(node['link_details'])}")
                
                if node['additional_capacity_needed'] > 0:
                    print(f"   - Recommendation: Add {node['additional_capacity_needed']}G additional capacity")
                    print(f"     (This could be achieved by adding more links or upgrading link speeds)")
        else:
            print(f"\nNo oversubscribed storage nodes found.")
            if "total_nodes" in analysis:
                print(f"Analyzed {analysis['total_nodes']} storage nodes.")
    
    # Handle switch pair ISL oversubscription
    if "total_switch_pairs" in analysis:
        print(f"\nFound {analysis['total_isls']} ISLs across {analysis['total_switch_pairs']} switch pairs in fabric.")
        
        if "oversubscribed_isls" in analysis and analysis["oversubscribed_isls"]:
            print(f"Detected {len(analysis['oversubscribed_isls'])} oversubscribed switch pairs:")
            
            for i, switch_pair_data in enumerate(analysis["oversubscribed_isls"], 1):
                print(f"\n{i}. Switch Pair {switch_pair_data['switch_pair']}:")
                print(f"   - Number of ISLs: {switch_pair_data['num_isls']}")
                print(f"   - Individual ISL speed: {switch_pair_data['individual_isl_speed']}G")
                print(f"   - Total capacity: {switch_pair_data['total_capacity']}G")
                print(f"   - Cumulative traffic: {switch_pair_data['traffic']}G")
                print(f"   - Oversubscription ratio: {switch_pair_data['ratio']:.2f}:1")
                
                if switch_pair_data['additional_capacity_needed'] > 0:
                    additional_isls = math.ceil(switch_pair_data['additional_capacity_needed'] / switch_pair_data['individual_isl_speed'])
                    print(f"   - Recommendation: Add {additional_isls} more ISL(s) of {switch_pair_data['individual_isl_speed']}G")
                
                # Show detailed ISL information
                print(f"   - ISL Details:")
                for j, isl in enumerate(switch_pair_data['all_isls']):
                    print(f"     ISL {j+1}: {isl['representative_wwpn']} (Switch {isl['switch_name']}:{isl['port_index']})")
        else:
            print("No oversubscribed switch pairs found.")
    # Handle traditional ISL oversubscription (fallback for old format)
    elif "total_isls" in analysis:
        print(f"\nFound {analysis['total_isls']} traditional ISLs in fabric.")
        
        if "oversubscribed_isls" in analysis and analysis["oversubscribed_isls"]:
            print(f"Detected {len(analysis['oversubscribed_isls'])} oversubscribed ISLs:")
            
            for i, isl in enumerate(analysis["oversubscribed_isls"], 1):
                # Display ISL connection information
                isl_pair = isl.get('connection_pair', (isl['wwpn'], isl.get('remote_wwpn', 'Unknown')))
                print(f"\n{i}. ISL Connection {isl_pair[0]} ↔ {isl_pair[1]}:")
                print(f"   - Primary port: {isl['wwpn']} (Switch {isl['switch_name']}:{isl['port_index']})")
                if 'remote_wwpn' in isl:
                    print(f"   - Remote port: {isl['remote_wwpn']}")
                print(f"   - Oversubscription ratio: {isl['ratio']:.2f}:1")
                print(f"   - ISL speed: {isl['speed']}G")
                print(f"   - Cumulative traffic: {isl['traffic']}G")
                
                if isl['additional_isls_needed'] > 0:
                    print(f"   - Recommendation: Add {isl['additional_isls_needed']} more ISL(s) of {isl['speed']}G")
        else:
            print("No oversubscribed traditional ISLs found.")
    
    # Special message for single-switch fabrics
    if "No traditional ISLs found" in analysis.get("status", ""):
        print("\nNote: This appears to be a single-switch fabric.")
        print("Oversubscription analysis focused on storage node connectivity.")
        if "total_nodes" in analysis:
            print(f"Analyzed connectivity to {analysis['total_nodes']} storage nodes.")

def find_shortest_path(graph, start, end):
    """
    Find the shortest path between two switches in the graph using BFS.
    
    Args:
        graph (dict): The switch connectivity graph
        start (str): The starting switch name
        end (str): The ending switch name
        
    Returns:
        list: The shortest path as a list of switch names, or None if no path exists
    """
    from collections import deque
    
    if start not in graph or end not in graph:
        return None
        
    if start == end:
        return [start]
        
    # Use BFS to find the shortest path
    queue = deque([(start, [start])])
    visited = set([start])
    
    while queue:
        current, path = queue.popleft()
        
        # Check all neighbors
        for neighbor in graph[current]:
            if neighbor == end:
                # Found the end
                return path + [neighbor]
                
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
                
    # No path found
    return None

def show_help():
    """Display help information."""
    print("\nHELP - FC SAN FABRIC MANAGEMENT")
    print("=" * 45)
    print("\nBASIC OPERATIONS:")
    print("   - List ports: View all registered initiators, targets, and switches")
    print("   - Check connectivity: Find path between two endpoints through fabric")
    print("   - Show topology: Display current fabric connections")
    print("   - Check ISL oversubscription: Analyze potential traffic through ISLs based on zoning")
    print("   - Help: Display this help information")
    print("\nWWPN FORMAT:")
    print("   - Standard FC format: XX:XX:XX:XX:XX:XX:XX:XX")
    print("   - Example: 10:00:00:00:c9:2b:9a:d1")
    print("\nFC PORT TYPES:")
    print("   - N-port: Node port (initiators/targets)")
    print("   - F-port: Fabric port (switch to device)")
    print("   - E-port: Expansion port (switch to switch ISL)")
    print("\nLINK SPEEDS:")
    print("   - Common speeds: 4Gb, 8Gb, 16Gb, 32Gb, 64Gb")
    print("   - Best practice: Maintain consistent speeds across the fabric")
    print("   - Note: Mismatched speeds result in connections operating at the lower speed")
    print("\nTIPS:")
    print("   - WWPN inputs are case-insensitive")
    print("   - Connections are bidirectional")
    print("   - ISLs are automatically detected between switches")

def run_interactive_cli():
    """Main interactive CLI loop."""
    display_banner()
    
    # Initialize topology to match the diagram
    print("\nInitializing SAN topology based on diagram...")
        # Main CLI loop
    while True:
        try:
            display_menu()
            choice = input("\nEnter your choice (0-5): ").strip()
            
            if choice == '1':
                list_all_ports()
            elif choice == '2':
                interactive_check_connectivity()
            elif choice == '3':
                show_all_connections()
            elif choice == '4':
                display_isl_oversubscription_analysis()
            elif choice == '5':
                show_help()
            elif choice == '0':
                print("\nThank you for using FC SAN Fabric Management System!")
                print("Exiting...")
                break
            else:
                print("Invalid choice. Please select from: 0, 1, 2, 3, 4, 5.")
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\nThank you for using FC SAN Fabric Management System!")
            print("Exiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            input("\nPress Enter to continue...")

def display_banner():
    """Display the CLI banner."""
    print("\n" + "="*80)
    print("              FC SAN FABRIC MANAGEMENT SYSTEM")
    print("              Interactive Command Line Interface")
    print("="*80)

def display_menu():
    """Display the main menu options."""
    print("\nMAIN MENU:")
    print("1. List all ports")
    print("2. Check fabric connectivity")
    print("3. Show current topology")
    print("4. Check ISL oversubscription")
    print("5. Help")
    print("0. Exit")
    print("-" * 50)

if __name__ == "__main__":
    print("Parsing showport, showhost, showportdev, and zoning output...")
    created_ports = parse_showport_output()

    # Parse node information and create TargetNode objects
    parse_node_information()

    # Establish switch connections
    establish_switch_connections()

    # Debug zoning info
    debug_zoning_info()
    
    
    run_interactive_cli()

    '''
    print(f"\nTotal ports created: {len(created_ports)}")
    print(f"Target ports dictionary size: {len(target_ports)}")
    print(f"Host ports dictionary size: {len(host_ports)}")
    print(f"Switch ports dictionary size: {len(switch_ports)}")
    print(f"Zoning info dictionary size: {len(zoning_info)}")
    print(f"Target nodes dictionary size: {len(target_nodes)}")
    
    # Show all registered ports
    print("\n=== Registered Ports ===")
    show_all_connections()
    
    # Display port details
    print("\n=== Port Details ===")
    for port in created_ports:
        print(f"Port ID: {port.port_id}, WWPN: {port.wwpn}, Type: {port.port_type}")
    
    # Display target_ports dictionary
    print(f"\ntarget port length - {len(target_ports)}")
    print("\n=== Target Ports Dictionary ===")
    for wwpn, port in target_ports.items():
        connection_info = f" -> Connected to: {port.connection}" if port.connection else " -> Not connected"
        print(f"WWPN: {wwpn} -> {port}{connection_info}")
    
    # Display host_ports dictionary
    print("\n=== Host Ports Dictionary ===")
    for wwpn, port in host_ports.items():
        connection_info = f" -> Connected to: {port.connection}" if port.connection else " -> Not connected"
        print(f"WWPN: {wwpn} -> {port}{connection_info}")
    
    # Display switch_ports dictionary
    print("\n=== Switch Ports Dictionary ===")
    for wwpn, port in switch_ports.items():
        connection_info = f" -> Connected to: {port.connection}" if port.connection else " -> Not connected"
        print(f"WWPN: {wwpn} -> {port}{connection_info}")
    
    # Display target_nodes dictionary
    print("\n=== Target Nodes Dictionary ===")
    for name, node in target_nodes.items():
        print(f"Name: {name} -> {node}")
    
    # Display initiator_nodes dictionary
    print("\n=== Initiator Nodes Dictionary ===")
    for name, node in initiator_nodes.items():
        print(f"Name: {name} -> {node}")
    
    # Display switch_nodes dictionary
    print("\n=== Switch Nodes Dictionary ===")
    for name, node in switch_nodes.items():
        print(f"Name: {name} -> {node}")
    
    # Display zoning_info dictionary
    print("\n=== Zoning Info Dictionary ===")
    for wwpn, zone_members in zoning_info.items():
        print(f"WWPN: {wwpn} -> Zone: {zone_members}")
    '''