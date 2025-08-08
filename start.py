from collections import deque
import math
import port_class
from port_class import (
    Port, Initiator, Target, Switch,
    register_port, connect_ports, disconnect_ports,
    initiator_index, target_index, switch_index
)

from node_class import TargetNode, SwitchNode, InitiatorNode, TargetArray

# Global dictionaries to store WWPN -> Port object mapping
target_ports = {}
host_ports = {}
switch_ports = {}
zoning_info = {}
all_zones = []
host_mapping = {}

# Global dictionaries to node objects info
# here info is mapped by host_name for initiators, node_name for targets, and switch_name for switches
target_nodes = {}
switch_nodes = {}
initiator_nodes = {}

# Global dictionary to store target arrays
target_arrays = {}

def parse_showsys_output(file_path="output 1.txt"):
    """
    Parse the showsys output and create TargetArray objects.
    
    Args:
        file_path (str): Path to the output file
    """
    global target_arrays
    
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        in_showsys_section = False
        
        for line in lines:
            line = line.strip()
            
            # Start reading after "showsys output:"
            if "showsys output:" in line:
                in_showsys_section = True
                print("Found showsys output section")
                continue
            
            # Stop when we hit another section
            if in_showsys_section and (line.startswith("showport") or line.startswith("showhost") or line.startswith("showportdev") or not line):
                in_showsys_section = False
                continue
            
            # Parse the showsys lines
            if in_showsys_section and "|" in line:
                # Split by | and clean up whitespace
                parts = [part.strip() for part in line.split("|")]
                
                if len(parts) >= 6:
                    wwnn = parts[0][2:]        # First column: WWNN
                    name = parts[1]          # Second column: Name
                    serial_number = parts[4] # Fifth column: Serial Number
                    node_count = parts[5]    # Sixth column: Node Count
                    
                    print(f"Found showsys data:")
                    print(f"  WWNN: {wwnn}")
                    print(f"  Name: {name}")
                    print(f"  Serial Number: {serial_number}")
                    print(f"  Node Count: {node_count}")
                    
                    try:
                        # Convert node_count to integer
                        node_count_int = int(node_count)
                        
                        # Create TargetArray object
                        target_array = TargetArray(
                            wwnn=wwnn,
                            name=name,
                            node_count=node_count_int,
                            serial_number=serial_number
                        )
                        
                        # Store in global dictionary with WWNN as key
                        target_arrays[wwnn] = target_array
                        print(f"Created TargetArray: {wwnn} -> {target_array}")
                        
                    except ValueError:
                        print(f"Warning: Could not convert node_count '{node_count}' to integer")
                        
                        # Create TargetArray object with string node_count as 0
                        target_array = TargetArray(
                            wwnn=wwnn,
                            name=name,
                            node_count=0,  # Default to 0 if conversion fails
                            serial_number=serial_number
                        )
                        
                        target_arrays[wwnn] = target_array
                        print(f"Created TargetArray with default node_count: {wwnn} -> {target_array}")
                
                else:
                    print(f"Warning: Insufficient columns in showsys line: {line}")
        
        print(f"\nTotal TargetArray objects created: {len(target_arrays)}")
        for wwnn, target_array in target_arrays.items():
            print(f"  {wwnn}: {target_array}")
    
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
    except Exception as e:
        print(f"Error parsing showsys output: {e}")

def parse_showport_output(file_path="output 1.txt"):
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
                    port_status = parts[2]      # Third column: status
                    wwnn = parts[3]             # Fourth column: WWNN  
                    wwpn = parts[4]             # Fifth column: WWPN
                    
                    # Log complete details for debugging
                    print(f"Found port in showport output: ID={port_id}, Type={port_type}, Status={port_status}, WWNN={wwnn}, WWPN={wwpn}")

                    # Create appropriate port object based on type
                    if port_type.lower() == "target":
                        # Extract the first value from port_id (e.g., "0" from "0:3:1")
                        node_number = port_id.split(':')[0] if ':' in port_id else port_id
                        array_name = None
                        wwnn_prefix = wwnn[11:]
                        if wwnn_prefix in target_arrays:
                            array_name = f"{target_arrays[wwnn_prefix].name}-node{node_number}"
                        else:
                            array_name = f"array-node{node_number}"
                        port = Target(
                            wwpn=wwpn,
                            port_id=port_id,
                            wwnn=wwnn,
                            speed="32Gbps",  # Default speed
                            array_name=array_name
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
                        port_index=port_index,
                        switch_port_type=switch_port_type  # E-Port, F-Port, etc.
                    )
                    
                    ports.append(switch_port)
                    if switch_ports.get(switch_wwpn) is None: switch_ports[switch_wwpn] = switch_port  # Add to switch_ports dictionary
                    register_port(switch_port)
                    print(f"Created switch port: Port={port_index}, WWPN={switch_wwpn}, Type={switch_port_type}")

                    # Check if this switch port already exists
                    if switch_wwpn in switch_ports:
                        # Port already exists - we'll keep only the first occurrence
                        # but still track the alternative connections for completeness
                        existing_port = switch_ports[switch_wwpn]
                        if not hasattr(existing_port, 'alt_connections'):
                            existing_port.alt_connections = []
                        
                        # Store the connection as an alternative if not already stored
                        if connection and connection not in existing_port.alt_connections:
                            existing_port.alt_connections.append(connection)
                            print(f"Added alternative connection for existing switch port {switch_wwpn}: {connection}")
                    else:
                        # First occurrence of this port - add it to the dictionary and port list
                        ports.append(switch_port)
                        switch_ports[switch_wwpn] = switch_port
                        switch_port.alt_connections = []  # Initialize empty alt_connections list
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

def parse_node_information(file_path="output 1.txt"):
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
        
        # Dictionary to store switch information dynamically
        switches = {}
        
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
                    
                    # Extract switch number and attribute from key
                    # Format: switch_1_name, switch_2_logical_name, etc.
                    if key.startswith("switch_") and "_" in key:
                        parts = key.split("_", 2)  # Split into max 3 parts: ['switch', '1', 'name']
                        if len(parts) >= 3:
                            switch_num = parts[1]
                            attribute = "_".join(parts[2:])  # Handle attributes like 'logical_name'
                            
                            # Initialize switch dictionary if it doesn't exist
                            if switch_num not in switches:
                                switches[switch_num] = {}
                            
                            # Store the attribute
                            switches[switch_num][attribute] = value
                            print(f"Set switch_{switch_num}.{attribute} to: {value}")
                            
                            # Check if we have all required attributes for this switch
                            required_attrs = ['name', 'vendor', 'model', 'release']
                            if all(attr in switches[switch_num] for attr in required_attrs):
                                # Create the switch node
                                print(f"\n=== Creating Switch Node {switch_num} ===")
                                
                                switch_data = switches[switch_num]
                                logical_name = switch_data.get('logical_name', f"switch_{switch_num}")
                                
                                switch_node = SwitchNode(
                                    name=logical_name,
                                    wwnn=switch_data['name'],
                                    release_version=switch_data['release'],
                                    model=switch_data['model'],
                                    port_count=None,  # Not available in current data
                                    vendor=switch_data['vendor']
                                )
                                
                                switch_nodes[logical_name] = switch_node
                                print(f"Created SwitchNode: {logical_name} with model={switch_data['model']}, vendor={switch_data['vendor']}")
        
        # Create TargetNode objects based on node_count
        if target_arrays:
            print(f"\n=== Creating Target Nodes from Target Arrays ===")
            
            for wwnn, target_array in target_arrays.items():
                array_name = target_array.name
                node_count = target_array.node_count
                target_array.software_version = node_version
                
                print(f"Processing array: {array_name} with {node_count} nodes")
                
                for i in range(node_count):
                    node_name = f"{array_name}-node{i}"
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
        
        # Summary of created switches
        if switches:
            print(f"\n=== Switch Creation Summary ===")
            print(f"Total switches processed: {len(switches)}")
            for switch_num, switch_data in switches.items():
                logical_name = switch_data.get('logical_name', f"switch_{switch_num}")
                print(f"Switch {switch_num}: {logical_name} ({switch_data.get('vendor', 'Unknown')} {switch_data.get('model', 'Unknown')})")
        
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
                    target_port.speed = switch_port.speed  # Set speed to match switch port
                    print(f"Connected switch {switch_wwpn} to target {connected_wwpn}")
                else:
                    print(f"Target {connected_wwpn} already connected to {target_port.connection}")
            
            # Search for the connected port in host_ports
            elif connected_wwpn in host_ports:
                host_port = host_ports[connected_wwpn]
                if host_port.connection is None:
                    host_port.connection = switch_wwpn
                    host_port.speed = switch_port.speed  # Set speed to match switch port
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

def connect_switches_internally():
    """
    Establish internal connections within switches and between switches via ISLs.
    This is crucial for proper path finding through the fabric.
    """
    global switch_index
    global test_path_switch_index
    global all_e_ports
    global switch_index
    
    print("\n=== Connecting Switches Internally ===")
    
    # Group switch ports by their switch name
    switch_groups = {}
    for wwpn, switch_port in switch_index.items():
        switch_name = switch_port.switch_name
        if switch_name not in switch_groups:
            switch_groups[switch_name] = []
        switch_groups[switch_name].append(wwpn)
    
    print(f"Found {len(switch_groups)} switches in fabric")
    
    # For each switch, connect all E-ports to all F-ports
    for switch_name, ports in switch_groups.items():
        print(f"Processing internal connections for switch: {switch_name}")
        f_ports = []  # Ports connected to devices (F-ports)
        e_ports = []  # Ports connected to other switches (E-ports)
        
        # Identify F-ports and E-ports
        for port_wwpn in ports:
            switch_port = switch_index[port_wwpn]
            if switch_port.is_connected():
                connected_port = get_port_by_wwpn(switch_port.connection)
                if connected_port:
                    # Check for port type in multiple ways
                    if isinstance(connected_port, (Initiator, Target)):
                        f_ports.append(port_wwpn)
                    elif isinstance(connected_port, Switch):
                        # Check port type explicitly if available
                        if hasattr(switch_port, 'switch_port_type'):
                            port_type = switch_port.switch_port_type.upper() if switch_port.switch_port_type else ""
                            if "E-PORT" in port_type or "E PORT" in port_type:
                                e_ports.append(port_wwpn)
                            else:
                                # For ports without explicit type, check connected switch name
                                if connected_port.switch_name != switch_port.switch_name:
                                    e_ports.append(port_wwpn)
                                else:
                                    f_ports.append(port_wwpn)
                        else:
                            # For ports without port_type attribute, check connected switch name
                            if connected_port.switch_name != switch_port.switch_name:
                                e_ports.append(port_wwpn)
                            else:
                                f_ports.append(port_wwpn)
        
        print(f"  Found {len(f_ports)} F-ports and {len(e_ports)} E-ports in switch {switch_name}")
        
        # Connect all ports to each other within the same switch
        all_ports = f_ports + e_ports
        for i, port1 in enumerate(all_ports):
            for port2 in all_ports[i+1:]:
                # Add bidirectional internal connections
                switch_port1 = switch_index[port1]
                switch_port2 = switch_index[port2]
                
                # Connect the ports (this will only set the internal adjacency connections)
                if port1 != port2:  # Avoid self-connections
                    connect_ports(port1, port2)
                    print(f"  Connected ports {port1} and {port2} in switch {switch_name}")
    
    # Now connect ports across ISLs (switch to switch connections)
    for wwpn, switch_port in switch_index.items():
        if hasattr(switch_port, 'switch_port_type') and switch_port.switch_port_type.upper() in ("E-PORT", "E PORT") and switch_port.is_connected():
            connected_port = get_port_by_wwpn(switch_port.connection)
            if connected_port and isinstance(connected_port, Switch):
                port_type1 = switch_port.switch_port_type if hasattr(switch_port, 'switch_port_type') else "Unknown"
                port_type2 = connected_port.switch_port_type if hasattr(connected_port, 'switch_port_type') else "Unknown"
                switch1 = switch_port.switch_name if hasattr(switch_port, 'switch_name') else "Unknown"
                switch2 = connected_port.switch_name if hasattr(connected_port, 'switch_name') else "Unknown"
                speed = switch_port.speed if hasattr(switch_port, 'speed') else "Unknown"
                
                print(f"Found ISL: {wwpn} ({port_type1}) -> {switch_port.connection} ({port_type2})")
                print(f"    Connection between switch {switch1} and {switch2} at {speed}")
                
                # Connect all ports in switch1 to all ports in switch2 through the ISL
                for port1_wwpn, port1 in switch_index.items():
                    if port1.switch_name == switch_port.switch_name and port1_wwpn != wwpn:
                        for port2_wwpn, port2 in switch_index.items():
                            if port2.switch_name == connected_port.switch_name and port2_wwpn != switch_port.connection:
                                # Create path through ISL
                                connect_ports(port1_wwpn, wwpn)
                                connect_ports(switch_port.connection, port2_wwpn)
                                print(f"  Established path: {port1_wwpn} -> {wwpn} -> {switch_port.connection} -> {port2_wwpn}")
    
    return True

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
            connection_status = "Connected" if initiator.is_connected() else "Not connected"
            connected_to = ""
            if initiator.is_connected():
                connected_port = get_port_by_wwpn(initiator.connection)
                if connected_port and isinstance(connected_port, Switch):
                    connected_to = f" to Switch {connected_port.switch_name}"
            print(f"   {wwpn} ({initiator.host_name}) - {connection_status}{connected_to}")
    
    if target_index:
        print("\nTargets:")
        for wwpn, target in target_index.items():
            connection_status = "Connected" if target.is_connected() else "Not connected"
            connected_to = ""
            if target.is_connected():
                connected_port = get_port_by_wwpn(target.connection)
                if connected_port and isinstance(connected_port, Switch):
                    connected_to = f" to Switch {connected_port.switch_name}"
            print(f"   {wwpn} ({target.array_name}) - {connection_status}{connected_to}")
    
    print("\nSwitches in fabric:")
    switch_names = set()
    for wwpn, switch_port in switch_index.items():
        switch_names.add(switch_port.switch_name)
    for switch_name in sorted(switch_names):
        print(f"   {switch_name}")
    
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
        if not source_port:
            print(f"Source port {source_wwpn} could not be found in any port registry")
        if not dest_port:
            print(f"Destination port {destination_wwpn} could not be found in any port registry")
        return False
        
    # Check if ports are properly initialized
    if not hasattr(source_port, 'connection') or not hasattr(dest_port, 'connection'):
        print("ERROR: One or both ports are not properly initialized")
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
        
        # Find switch boundaries for better visualization of ISL crossings
        switch_transitions = []
        current_switch = None
        
        for i, wwpn in enumerate(path):
            port = get_port_by_wwpn(wwpn)
            if isinstance(port, Switch):
                switch_name = getattr(port, 'switch_name', None)
                if switch_name and switch_name != current_switch:
                    if current_switch is not None:  # Not the first switch
                        switch_transitions.append(i)
                    current_switch = switch_name
        
        # Print path with enhanced ISL visibility
        for i, wwpn in enumerate(path):
            port = get_port_by_wwpn(wwpn)
            port_info = ""
            
            # Create descriptive port info
            if isinstance(port, Initiator):
                port_info = f"Initiator ({port.host_name})"
            elif isinstance(port, Target):
                port_info = f"Target ({port.array_name})"
            elif isinstance(port, Switch):
                port_info = f"Switch ({port.switch_name}:{port.port_index})"
                if hasattr(port, 'switch_port_type') and port.switch_port_type:
                    # Determine port type based on connection
                    display_port_type = port.switch_port_type.upper()
                    
                    # Check next port in path - if it's a switch in a different chassis, it's an E-PORT (ISL)
                    if i < len(path) - 1:
                        next_port = get_port_by_wwpn(path[i+1])
                        if isinstance(next_port, Switch) and hasattr(next_port, 'switch_name') and hasattr(port, 'switch_name'):
                            if port.switch_name != next_port.switch_name:
                                display_port_type = "E-PORT"
                    
                    # Check previous port in path - if it's a switch in a different chassis, it's an E-PORT (ISL)
                    if i > 0:
                        prev_port = get_port_by_wwpn(path[i-1])
                        if isinstance(prev_port, Switch) and hasattr(prev_port, 'switch_name') and hasattr(port, 'switch_name'):
                            if port.switch_name != prev_port.switch_name:
                                display_port_type = "E-PORT"
                    
                    # Check if it connects to a target - should be F-PORT
                    if i < len(path) - 1 and isinstance(get_port_by_wwpn(path[i+1]), Target):
                        display_port_type = "F-PORT"
                    
                    # Check if it connects to an initiator - should be F-PORT
                    if i > 0 and isinstance(get_port_by_wwpn(path[i-1]), Initiator):
                        display_port_type = "F-PORT"
                    
                    port_info += f" [{display_port_type}]"
            
            # Add speed information
            port_info += f" - {port.speed}"
            
            # Special formatting for ISL connections
            is_isl_entry = False
            is_isl_exit = False
            
            # Determine if this is an ISL entry or exit point
            if isinstance(port, Switch) and hasattr(port, 'switch_port_type'):
                if i < len(path) - 1:
                    next_port = get_port_by_wwpn(path[i+1])
                    if isinstance(next_port, Switch) and hasattr(next_port, 'switch_port_type'):
                        if (port.switch_name != next_port.switch_name or  # Different switches
                            (hasattr(port, 'switch_port_type') and 'E-PORT' in port.switch_port_type.upper()) or
                            (hasattr(next_port, 'switch_port_type') and 'E-PORT' in next_port.switch_port_type.upper())):
                            is_isl_exit = True
                
                if i > 0:
                    prev_port = get_port_by_wwpn(path[i-1])
                    if isinstance(prev_port, Switch) and hasattr(prev_port, 'switch_port_type'):
                        if (port.switch_name != prev_port.switch_name or  # Different switches
                            (hasattr(port, 'switch_port_type') and 'E-PORT' in port.switch_port_type.upper()) or
                            (hasattr(prev_port, 'switch_port_type') and 'E-PORT' in prev_port.switch_port_type.upper())):
                            is_isl_entry = True
            
            # Output with connection information
            if i < len(path) - 1:
                next_port = get_port_by_wwpn(path[i+1])
                
                # Show speed connection info
                speed_info = f" ({port.speed} → {next_port.speed})"
                
                # Base output
                output_line = f"  {i+1}. {wwpn} - {port_info} connected to {next_port.wwpn}{speed_info}"
                print(output_line)
                
                # Special ISL crossing indicator
                if i+1 in switch_transitions:
                    # Get the ISL port details for current and next port
                    port_details = f"{port.wwpn}"
                    next_port_details = f"{next_port.wwpn}"
                    
                    if hasattr(port, 'switch_port_type'):
                        port_details += f" ({port.switch_port_type})"
                    if hasattr(next_port, 'switch_port_type'):
                        next_port_details += f" ({next_port.switch_port_type})"
                    
                    print(f"     |")
                    print(f"     ⭇ ISL CROSSING - Inter-Switch Link ⭆")
                    # Replace both F-PORT and F-Port with E-PORT or E-Port respectively
                    port_details = port_details.replace('F-PORT', 'E-PORT').replace('F-Port', 'E-Port')
                    next_port_details = next_port_details.replace('F-PORT', 'E-PORT').replace('F-Port', 'E-Port')
                    print(f"       From: {port_details} -> To: {next_port_details}")
                    print(f"     |")
                elif is_isl_exit:
                    port_type = getattr(port, 'switch_port_type', 'E-PORT')
                    print(f"     | (Exiting switch via E-PORT: {port.wwpn})")
                elif is_isl_entry:
                    port_type = getattr(port, 'switch_port_type', 'E-PORT')
                    print(f"     | (Entering switch via E-PORT: {port.wwpn})")
                else:
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
    from collections import deque
    source_port = get_port_by_wwpn(source_wwpn)
    dest_port = get_port_by_wwpn(destination_wwpn)
    
    if not source_port or not dest_port:
        print(f"Error: Could not find source ({source_wwpn}) or destination ({destination_wwpn}) port")
        return None
    
    # Check if both are endpoints (initiator or target)
    if not (isinstance(source_port, (Initiator, Target)) and isinstance(dest_port, (Initiator, Target))):
        print(f"Error: Both source and destination must be initiators or targets")
        return None
        
    # Ensure that switches are properly connected internally for path finding
    # This helps establish paths within switches and between switches
    connect_switches_internally()
    
    print(f"\nAnalyzing path from {source_wwpn} to {destination_wwpn}")
    
    # Build adjacency list from current connections
    adjacency = {}
    
    # Group switch ports by their actual switch identity (not WWNN)
    # We need to identify which ports belong to the same physical switch
    switch_groups = {}
    
    for wwpn, switch_port in switch_index.items():
        # Group by switch name which is more reliable than WWPN prefixes
        switch_name = switch_port.switch_name
        if switch_name not in switch_groups:
            switch_groups[switch_name] = []
        switch_groups[switch_name].append(wwpn)
    
    print(f"\nFound {len(switch_groups)} switches in fabric")
    for switch_name, ports in switch_groups.items():
        print(f"  Switch {switch_name}: {len(ports)} ports")
    
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
    
    # Special handling for ISL connections (switch-to-switch)
    # Find all E-ports and ensure they're properly connected
    isl_connections = []
    for wwpn, switch_port in switch_index.items():
        if (hasattr(switch_port, 'switch_port_type') and 
            (switch_port.switch_port_type == 'E-Port' or switch_port.switch_port_type == 'E-port') and 
            switch_port.is_connected()):
            connected_wwpn = switch_port.connection
            connected_port = get_port_by_wwpn(connected_wwpn)
            if connected_port and isinstance(connected_port, Switch):
                isl_connections.append((wwpn, connected_wwpn))
                
                # Make sure the connection is bidirectional in the adjacency list
                if wwpn not in adjacency:
                    adjacency[wwpn] = []
                if connected_wwpn not in adjacency[wwpn]:
                    adjacency[wwpn].append(connected_wwpn)
                    
                if connected_wwpn not in adjacency:
                    adjacency[connected_wwpn] = []
                if wwpn not in adjacency[connected_wwpn]:
                    adjacency[connected_wwpn].append(wwpn)
                
                # Track the switches these ports belong to for cross-fabric connections
                switch1_name = switch_port.switch_name if hasattr(switch_port, 'switch_name') else None
                switch2_name = connected_port.switch_name if hasattr(connected_port, 'switch_name') else None
                
                if switch1_name and switch2_name and switch1_name != switch2_name:
                    print(f"Found ISL: {wwpn} -> {connected_wwpn}")
    
    print(f"Found {len(isl_connections)} ISL connections between switches")
    
    # Now add internal switch connections, but only between F-ports and E-ports
    # This models how traffic can enter through F-port and exit through E-port (or vice versa)
    
    # Keep track of all E-ports for cross-fabric connections
    all_e_ports = []
    all_f_ports = []
    e_port_to_switch_map = {}  # Map E-ports to their switch name
    f_port_to_switch_map = {}  # Map F-ports to their switch name
    
    for switch_name, ports in switch_groups.items():
        print(f"Processing internal connections for switch: {switch_name}")
        f_ports = []  # Ports connected to devices (F-ports)
        e_ports = []  # Ports connected to other switches (E-ports)
        
        for port_wwpn in ports:
            switch_port = switch_index[port_wwpn]
            if switch_port.is_connected():
                connected_port = get_port_by_wwpn(switch_port.connection)
                if connected_port:
                    # Check for port type in multiple ways
                    if isinstance(connected_port, (Initiator, Target)):
                        f_ports.append(port_wwpn)  # This is an F-port
                        f_port_to_switch_map[port_wwpn] = switch_name
                        all_f_ports.append(port_wwpn)
                    elif isinstance(connected_port, Switch):
                        # Check port type explicitly if available
                        if hasattr(switch_port, 'switch_port_type'):
                            port_type = switch_port.switch_port_type.upper() if switch_port.switch_port_type else ""
                            if "F-PORT" in port_type:
                                f_ports.append(port_wwpn)
                                f_port_to_switch_map[port_wwpn] = switch_name
                                all_f_ports.append(port_wwpn)
                            elif "E-PORT" in port_type:
                                e_ports.append(port_wwpn)  # This is an E-port (ISL)
                                e_port_to_switch_map[port_wwpn] = switch_name
                                all_e_ports.append(port_wwpn)
                            else:
                                # For ports without explicit type, check connected switch name
                                if connected_port.switch_name != switch_port.switch_name:
                                    e_ports.append(port_wwpn)  # This is an E-port (ISL)
                                    e_port_to_switch_map[port_wwpn] = switch_name
                                    all_e_ports.append(port_wwpn)
                                else:
                                    f_ports.append(port_wwpn)  # Same switch, treat as F-port
                                    f_port_to_switch_map[port_wwpn] = switch_name
                                    all_f_ports.append(port_wwpn)
                        else:
                            # For ports without port_type attribute, check connected switch name
                            if connected_port.switch_name != switch_port.switch_name:
                                e_ports.append(port_wwpn)  # Different switches - E-port
                                e_port_to_switch_map[port_wwpn] = switch_name
                                all_e_ports.append(port_wwpn)
                            else:
                                f_ports.append(port_wwpn)  # Same switch, treat as F-port
                                f_port_to_switch_map[port_wwpn] = switch_name
                                all_f_ports.append(port_wwpn)
        
        # Connect F-ports to E-ports (allowing traffic to flow through the switch)
        for f_port in f_ports:
            for e_port in e_ports:
                # Add bidirectional internal switch connections
                if f_port != e_port:  # Avoid self-loops
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
    
    # Also connect F-ports to each other within the same switch for direct device-to-device communication
        for i, f_port1 in enumerate(f_ports):
            for f_port2 in f_ports[i+1:]:
                if f_port1 != f_port2:  # Avoid self-loops
                    if f_port1 not in adjacency:
                        adjacency[f_port1] = []
                    if f_port2 not in adjacency[f_port1]:
                        adjacency[f_port1].append(f_port2)
                    
                    if f_port2 not in adjacency:
                        adjacency[f_port2] = []
                    if f_port1 not in adjacency[f_port2]:
                        adjacency[f_port2].append(f_port1)
                        
    # Now connect across fabrics through ISLs
    # Find all ISL pairs - fix: be more lenient with ISL detection
    
    isl_pairs = []
    
    # If in test path mode, we need to identify ISLs directly from the switch ports
    # This is important because all_e_ports might not be properly populated in test-path mode
    
    # Determine which switch_index to use
    switches_to_use = test_path_switch_index if 'test_path_switch_index' in globals() and test_path_switch_index is not None else switch_index
    
    # First, identify all E-ports from the switch ports directly (to handle test-path mode)
    direct_e_ports = []
    for wwpn, switch_port in switches_to_use.items():
        if hasattr(switch_port, 'switch_port_type') and switch_port.switch_port_type == 'E-Port':
            direct_e_ports.append(wwpn)
            print(f"Found direct E-port: {wwpn} (type: {switch_port.switch_port_type})")
    
    # Use direct_e_ports if we're in test-path mode and all_e_ports is empty
    e_ports_to_check = direct_e_ports if 'test_path_switch_index' in globals() and test_path_switch_index is not None else all_e_ports
    
    # If direct_e_ports has entries but all_e_ports doesn't, use direct_e_ports
    if len(direct_e_ports) > 0 and len(all_e_ports) == 0:
        e_ports_to_check = direct_e_ports
        print(f"Using {len(direct_e_ports)} directly detected E-ports instead of all_e_ports (which has {len(all_e_ports)})")
    
    for e_port in e_ports_to_check:
        if e_port in switches_to_use and switches_to_use[e_port].is_connected():
            connected_wwpn = switches_to_use[e_port].connection
            # Verify this is a connection between two switches (more relaxed criteria)
            if connected_wwpn in switches_to_use:
                connected_port = switches_to_use[connected_wwpn]
                # Check if this connects two different switches
                if (hasattr(switches_to_use[e_port], 'switch_name') and 
                    hasattr(connected_port, 'switch_name') and
                    switches_to_use[e_port].switch_name != connected_port.switch_name):
                    print(f"Detected ISL between different switches: {e_port} ({switches_to_use[e_port].switch_name}) -> "
                          f"{connected_wwpn} ({connected_port.switch_name})")
                    isl_pairs.append((e_port, connected_wwpn))
    
    print(f"Found {len(isl_pairs)} ISL pairs between switches")
    
    # For each ISL pair, connect all F-ports on one side to all F-ports on the other side
    for e_port1, e_port2 in isl_pairs:
        switch1 = e_port_to_switch_map.get(e_port1)
        switch2 = e_port_to_switch_map.get(e_port2)
        
        if switch1 and switch2 and switch1 != switch2:
            print(f"Creating cross-switch paths between {switch1} and {switch2}")
            # Get all F-ports for each switch
            switch1_f_ports = [p for p in all_f_ports if f_port_to_switch_map.get(p) == switch1]
            switch2_f_ports = [p for p in all_f_ports if f_port_to_switch_map.get(p) == switch2]
            
            print(f"  Switch {switch1} has {len(switch1_f_ports)} F-ports")
            print(f"  Switch {switch2} has {len(switch2_f_ports)} F-ports")
            
            # Create direct connections between ISL ports
            # Connect e_port1 directly to e_port2 (bidirectional)
            if e_port1 not in adjacency:
                adjacency[e_port1] = []
            if e_port2 not in adjacency[e_port1]:
                adjacency[e_port1].append(e_port2)
                print(f"  Connected ISL endpoints: {e_port1} -> {e_port2}")
            
            if e_port2 not in adjacency:
                adjacency[e_port2] = []
            if e_port1 not in adjacency[e_port2]:
                adjacency[e_port2].append(e_port1)
                print(f"  Connected ISL endpoints: {e_port2} -> {e_port1}")
            
            # Connect each F-port on switch1 to e_port1 (the local ISL endpoint)
            for f_port1 in switch1_f_ports:
                if f_port1 not in adjacency:
                    adjacency[f_port1] = []
                if e_port1 not in adjacency[f_port1]:
                    adjacency[f_port1].append(e_port1)
                
                if e_port1 not in adjacency:
                    adjacency[e_port1] = []
                if f_port1 not in adjacency[e_port1]:
                    adjacency[e_port1].append(f_port1)
                    
                print(f"  Connected within switch {switch1}: {f_port1} <-> {e_port1}")
                
            # Connect each F-port on switch2 to e_port2 (the local ISL endpoint)
            for f_port2 in switch2_f_ports:
                if f_port2 not in adjacency:
                    adjacency[f_port2] = []
                if e_port2 not in adjacency[f_port2]:
                    adjacency[f_port2].append(e_port2)
                
                if e_port2 not in adjacency:
                    adjacency[e_port2] = []
                if f_port2 not in adjacency[e_port2]:
                    adjacency[e_port2].append(f_port2)
                    
                print(f"  Connected within switch {switch2}: {f_port2} <-> {e_port2}")
            
            # Also directly connect F-ports across switches for more robust path finding
            for f_port1 in switch1_f_ports:
                device1 = None
                if f_port1 in switch_index and switch_index[f_port1].connection:
                    device1_wwpn = switch_index[f_port1].connection
                    if device1_wwpn in initiator_index or device1_wwpn in target_index:
                        device1 = device1_wwpn
                
                for f_port2 in switch2_f_ports:
                    device2 = None
                    if f_port2 in switch_index and switch_index[f_port2].connection:
                        device2_wwpn = switch_index[f_port2].connection
                        if device2_wwpn in initiator_index or device2_wwpn in target_index:
                            device2 = device2_wwpn
                    
                    # If this is a specific initiator-target pair we're trying to connect,
                    # create a more direct path
                    if (device1 and device2 and 
                        ((device1 == source_wwpn and device2 == destination_wwpn) or 
                         (device2 == source_wwpn and device1 == destination_wwpn))):
                        print(f"  Creating direct cross-switch path for target pair: {device1} <-> {device2}")
                        
                        # Create bidirectional paths for all segments
                        # device1 <-> f_port1 <-> e_port1 <-> e_port2 <-> f_port2 <-> device2
                        
                        # Add missing connections to ensure complete path
                        for p1, p2 in [(device1, f_port1), (f_port1, e_port1), 
                                       (e_port1, e_port2), (e_port2, f_port2), (f_port2, device2)]:
                            if p1 not in adjacency:
                                adjacency[p1] = []
                            if p2 not in adjacency[p1]:
                                adjacency[p1].append(p2)
                                
                            if p2 not in adjacency:
                                adjacency[p2] = []
                            if p1 not in adjacency[p2]:
                                adjacency[p2].append(p1)
                                
                        print(f"  Direct path created: {device1} <-> {f_port1} <-> {e_port1} <-> {e_port2} <-> {f_port2} <-> {device2}")
    
    # Output debug info about the adjacency list
    print(f"\nBuilt adjacency list with {len(adjacency)} ports")
    
    # Print a sample of the adjacency list for debugging
    sample_count = 0
    print("Sample of adjacency list (showing up to 10 entries):")
    for port, connections in adjacency.items():
        port_obj = get_port_by_wwpn(port)
        port_type = "Unknown"
        port_info = ""
        
        if port_obj:
            if isinstance(port_obj, Initiator): 
                port_type = "Initiator"
                port_info = f"({port_obj.host_name})"
            elif isinstance(port_obj, Target): 
                port_type = "Target"
                port_info = f"({port_obj.array_name})"
            elif isinstance(port_obj, Switch): 
                port_type = "Switch"
                port_info = f"({port_obj.switch_name}:{port_obj.port_index})"
            
            print(f"  {port} ({port_type}{' ' + port_info if port_info else ''}) -> {connections}")
            
            sample_count += 1
            if sample_count >= 10:
                break
    
    # Use BFS to find shortest path through the fabric
    queue = deque([(source_wwpn, [source_wwpn])])
    visited = set([source_wwpn])
    
    print(f"\nStarting BFS path search from {source_wwpn} to {destination_wwpn}")
    
    # Determine if both endpoints have connections to switches
    source_port = get_port_by_wwpn(source_wwpn)
    dest_port = get_port_by_wwpn(destination_wwpn)
    source_switch_wwpn = source_port.connection if source_port and source_port.is_connected() else None
    dest_switch_wwpn = dest_port.connection if dest_port and dest_port.is_connected() else None
    
    # Print valuable debug info about endpoint connections
    print(f"Source {source_wwpn} is connected to switch port: {source_switch_wwpn}")
    print(f"Destination {destination_wwpn} is connected to switch port: {dest_switch_wwpn}")
    
    # Create direct source to switch connection if needed
    if source_wwpn not in adjacency and source_switch_wwpn:
        adjacency[source_wwpn] = [source_switch_wwpn]
        print(f"Added direct source to switch connection: {source_wwpn} -> {source_switch_wwpn}")
    
    # Create direct destination to switch connection if needed
    if destination_wwpn not in adjacency and dest_switch_wwpn:
        adjacency[destination_wwpn] = [dest_switch_wwpn]
        print(f"Added direct destination to switch connection: {destination_wwpn} -> {dest_switch_wwpn}")
    
    # Perform the BFS search
    print("Starting BFS search...")
    visited_detail = {}  # Track which ports we visited and their neighbors
    
    while queue:
        current_wwpn, path = queue.popleft()
        
        # Print current position in the search
        port_obj = get_port_by_wwpn(current_wwpn)
        port_type = "Unknown"
        if port_obj:
            port_type = port_obj.__class__.__name__
            if hasattr(port_obj, 'switch_name'):
                port_type += f" ({port_obj.switch_name})"
        print(f"  Visiting: {current_wwpn} ({port_type}), path length: {len(path)}")
        
        # We reached our destination
        if current_wwpn == destination_wwpn:
            print(f"SUCCESS! Found path of length {len(path)} from {source_wwpn} to {destination_wwpn}")
            # Print the full path for debugging
            print(f"Full path: {path}")
            return path
        
        # Explore all neighbors
        if current_wwpn in adjacency:
            neighbors = adjacency[current_wwpn]
            visited_detail[current_wwpn] = neighbors
            print(f"    Neighbors ({len(neighbors)}): {neighbors}")
            
            for neighbor_wwpn in neighbors:
                if neighbor_wwpn not in visited:
                    visited.add(neighbor_wwpn)
                    new_path = path + [neighbor_wwpn]
                    queue.append((neighbor_wwpn, new_path))
                    neighbor_obj = get_port_by_wwpn(neighbor_wwpn)
                    neighbor_type = "Unknown"
                    if neighbor_obj:
                        neighbor_type = neighbor_obj.__class__.__name__
                        if hasattr(neighbor_obj, 'switch_name'):
                            neighbor_type += f" ({neighbor_obj.switch_name})"
                    print(f"      Adding to queue: {neighbor_wwpn} ({neighbor_type})")
        else:
            print(f"    No neighbors found for {current_wwpn}")
            visited_detail[current_wwpn] = []
    
    # No path found - provide detailed diagnostic info
    print("\nNo path found between endpoints")
    print(f"Starting from {source_wwpn}, visited {len(visited)} ports")
    
    # Analyze why path finding failed
    print("\nDiagnostic information:")
    
    # Check if both endpoints are in the adjacency list
    if source_wwpn not in adjacency:
        print(f"ERROR: Source endpoint {source_wwpn} is not in the adjacency list")
    if destination_wwpn not in adjacency:
        print(f"ERROR: Destination endpoint {destination_wwpn} is not in the adjacency list")
    
    # Check if there are any switch-to-switch connections
    switch_to_switch = 0
    for wwpn, neighbors in adjacency.items():
        port = get_port_by_wwpn(wwpn)
        if port and isinstance(port, Switch):
            for neighbor in neighbors:
                neighbor_port = get_port_by_wwpn(neighbor)
                if neighbor_port and isinstance(neighbor_port, Switch):
                    switch_to_switch += 1
    
    print(f"Found {switch_to_switch} switch-to-switch connections in adjacency list")
    
    # Print the most important parts of the visited path
    print("\nPath exploration summary:")
    visited_switches = set()
    
    for wwpn in visited:
        port = get_port_by_wwpn(wwpn)
        if port and isinstance(port, Switch) and hasattr(port, 'switch_name'):
            visited_switches.add(port.switch_name)
    
    print(f"Visited {len(visited_switches)} unique switches: {sorted(visited_switches)}")
    
    # Check if endpoint's switches were visited
    if source_switch_wwpn:
        source_switch = get_port_by_wwpn(source_switch_wwpn)
        if source_switch and hasattr(source_switch, 'switch_name'):
            if source_switch.switch_name in visited_switches:
                print(f"Source switch {source_switch.switch_name} was visited")
            else:
                print(f"ERROR: Source switch {source_switch.switch_name} was NOT visited!")
    
    if dest_switch_wwpn:
        dest_switch = get_port_by_wwpn(dest_switch_wwpn)
        if dest_switch and hasattr(dest_switch, 'switch_name'):
            if dest_switch.switch_name in visited_switches:
                print(f"Destination switch {dest_switch.switch_name} was visited")
            else:
                print(f"ERROR: Destination switch {dest_switch.switch_name} was NOT visited!")
                
    # Try a fallback direct path as last resort
    if source_switch_wwpn and dest_switch_wwpn:
        print("\nAttempting fallback direct path creation...")
        # Create direct source to destination path if both are connected to switches
        source_switch = get_port_by_wwpn(source_switch_wwpn)
        dest_switch = get_port_by_wwpn(dest_switch_wwpn)
        
        if (source_switch and dest_switch and 
            hasattr(source_switch, 'switch_name') and hasattr(dest_switch, 'switch_name')):
            
            print(f"Creating direct path: {source_wwpn} -> {source_switch_wwpn} -> {dest_switch_wwpn} -> {destination_wwpn}")
            fallback_path = [source_wwpn, source_switch_wwpn, dest_switch_wwpn, destination_wwpn]
            print("WARNING: Using fallback path - connectivity may not be physically possible")
            return fallback_path
    
    # Print additional debug info about source and destination
    print("\nSource port details:")
    print(f"  Type: {source_port.__class__.__name__}")
    print(f"  Connected to: {source_port.connection}")
    if source_port.connection:
        connected_port = get_port_by_wwpn(source_port.connection)
        if connected_port:
            print(f"  Connected port type: {connected_port.__class__.__name__}")
            if isinstance(connected_port, Switch) and hasattr(connected_port, 'switch_port_type'):
                print(f"  Connected port switch type: {connected_port.switch_port_type}")
                print(f"  Connected switch name: {connected_port.switch_name}")
    
    print("\nDestination port details:")
    print(f"  Type: {dest_port.__class__.__name__}")
    print(f"  Connected to: {dest_port.connection}")
    if dest_port.connection:
        connected_port = get_port_by_wwpn(dest_port.connection)
        if connected_port:
            print(f"  Connected port type: {connected_port.__class__.__name__}")
            if isinstance(connected_port, Switch) and hasattr(connected_port, 'switch_port_type'):
                print(f"  Connected port switch type: {connected_port.switch_port_type}")
                print(f"  Connected switch name: {connected_port.switch_name}")
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
    global target_ports
    global test_path_target_ports
    global all_zones 
    global test_path_all_zones
    global switch_index
    global test_path_switch_index
    global test_path_mode
    
    # Dictionary to track traffic per target node: {node_id: traffic}
    node_traffic = {}
    
    # Dictionary to track links per target node: {node_id: {link_speed: count}}
    node_links = {}
    
    # Dictionary to store node details
    node_details = {}
    
    # Analyze target ports to identify nodes and their connections
    # Make sure we access the correct global variable based on context
    global target_ports
    global test_path_target_ports
    
    # Determine which target_ports to use based on context
    ports_to_use = test_path_target_ports if 'test_path_target_ports' in globals() and test_path_target_ports is not None else target_ports
    
    for wwpn, target_port in ports_to_use.items():
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
    # Make sure we access the correct global variable based on context
    
    # Use test_path_all_zones if in test-path mode, otherwise use all_zones
    if 'test_path_all_zones' in globals() and test_path_all_zones is not None:
        zones = test_path_all_zones  # Use test path specific zones
    else:
        zones = all_zones  # Use the correctly parsed zones directly
    
    # Process each zone to calculate traffic
    for zone_members in zones:
        # Identify all initiators and targets in this zone
        initiators = []
        targets = []
        
        for wwpn in zone_members:
            # In test-path mode, we should use test_path_get_port_by_wwpn if available
            if 'test_path_mode' in globals() and test_path_mode and 'test_path_get_port_by_wwpn' in globals():
                port = test_path_get_port_by_wwpn(wwpn)
            else:
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
    isl_traffic = {}       # Track traffic across ISLs
    isl_details = {}       # Store details about each ISL
    
    # Find all switch-to-switch connections (ISLs) and group by switch pairs
    # Access global variables defined at the beginning of the function
    
    # Determine which switch_index to use based on context
    switches_to_use = test_path_switch_index if 'test_path_switch_index' in globals() and test_path_switch_index is not None else switch_index
    
    # Enhanced debugging to understand the test-path mode environment
    if 'test_path_switch_index' in globals() and test_path_switch_index is not None:
        print(f"Running in test-path mode with {len(test_path_switch_index)} switch ports")
        
        try:
            # Try to import our new helper function
            from find_e_ports import find_e_ports_in_data
            
            # Use it to find E-ports directly
            direct_e_ports = find_e_ports_in_data(test_path_switch_index)
            print(f"Found {len(direct_e_ports)} E-ports directly in switch data")
            
            # If we found E-ports, make sure we'll use them later in the analysis
            if direct_e_ports:
                # Force direct detection of ISLs from E-ports
                for e_port_wwpn in direct_e_ports:
                    port = switches_to_use.get(e_port_wwpn)
                    if port and hasattr(port, 'connection'):
                        print(f"ISL direct detection: {e_port_wwpn} -> {port.connection}")
        except ImportError:
            print("Could not import find_e_ports helper module")
        
        # Count how many E-ports we have in switch_index
        e_port_count = 0
        for wwpn, port in test_path_switch_index.items():
            if hasattr(port, 'switch_port_type') and port.switch_port_type == 'E-Port':
                e_port_count += 1
                print(f"Found E-port in test_path_switch_index: {wwpn}, connecting {port.switch_name} to {port.connection}")
        print(f"Found {e_port_count} E-ports in test_path_switch_index")
    
    for wwpn, switch_port in switches_to_use.items():
        # Check if this port connects to another switch
        if switch_port.is_connected():
            # Get the connected port using the appropriate function based on context
            if 'test_path_mode' in globals() and test_path_mode and 'test_path_get_port_by_wwpn' in globals():
                connected_port = test_path_get_port_by_wwpn(switch_port.connection)
            else:
                connected_port = get_port_by_wwpn(switch_port.connection)
                
            if connected_port and isinstance(connected_port, Switch):
                is_isl = False
                
                # Check if it's explicitly marked as E-Port or has E-Port characteristics
                if hasattr(switch_port, 'switch_port_type'):
                    port_type_str = str(switch_port.switch_port_type).strip().upper()
                    print(f"Checking port type: '{port_type_str}'")
                    
                    # Check for E-Port type (be more flexible with matching)
                    if 'E-PORT' in port_type_str.upper() or 'E PORT' in port_type_str.upper() or 'EPORT' in port_type_str.upper():
                        print(f"Detected ISL by E-Port type: {wwpn} ({switch_port.switch_name}) -> {switch_port.connection}")
                        is_isl = True
                    # Check if switches are different (which would indicate an ISL)
                    elif hasattr(switch_port, 'switch_name') and hasattr(connected_port, 'switch_name'):
                        switch1 = str(switch_port.switch_name).strip()
                        switch2 = str(connected_port.switch_name).strip()
                        
                        if switch1 != switch2:
                            # Different switch names indicates this is an ISL
                            print(f"Detected ISL by switch name difference: {switch1} to {switch2}")
                            is_isl = True
                
                if not is_isl:
                    continue
                
                # Identify the switch pair using switch names for more reliability
                switch1_name = str(switch_port.switch_name).strip() if hasattr(switch_port, 'switch_name') else "Unknown"
                switch2_name = str(connected_port.switch_name).strip() if hasattr(connected_port, 'switch_name') else "Unknown"
                
                # Skip if it's connecting to itself (not a true ISL) or we don't have valid switch names
                if switch1_name == switch2_name or switch1_name == "Unknown" or switch2_name == "Unknown":
                    continue
                    
                # Create a unique tuple for this switch pair
                switch_pair = tuple(sorted([switch1_name, switch2_name]))
                print(f"Found ISL between: {switch1_name} and {switch2_name}, port: {getattr(switch_port, 'port_index', 'Unknown')}, type: {getattr(switch_port, 'switch_port_type', 'Unknown')}")
                
                # Debug the switch pair creation
                print(f"Creating switch pair key: {switch_pair}")
                
                # Initialize switch pair if not seen before
                if switch_pair not in switch_pair_isls:
                    print(f"Initializing new switch pair in tracking dictionary: {switch_pair}")
                    switch_pair_isls[switch_pair] = {
                        "isls": [],
                        "total_capacity": 0,
                        "traffic": 0,
                        "switch_names": switch_pair
                    }
                
                # Also make sure it's initialized in isl_traffic and isl_details
                if switch_pair not in isl_traffic:
                    isl_traffic[switch_pair] = 0
                    
                if switch_pair not in isl_details:
                    isl_details[switch_pair] = switch_pair_isls[switch_pair]
                
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
                        "switch_name": str(switch_port.switch_name).strip(),
                        "port_index": switch_port.port_index,
                        "port_type": getattr(switch_port, 'switch_port_type', 'Unknown'),
                        "remote_wwpn": switch_port.connection,
                        "remote_switch_name": str(connected_port.switch_name).strip()
                    }
                    
                    switch_pair_isls[switch_pair]["isls"].append(isl_info)
                    switch_pair_isls[switch_pair]["total_capacity"] += speed_value
                    
                    print(f"Added ISL {isl_pair} to switch pair {switch_pair}, capacity now: {switch_pair_isls[switch_pair]['total_capacity']}Gb")
                    
                    # Initialize traffic counter for this ISL pair
                    isl_traffic[switch_pair] = 0
                    
                    # Keep track of the details for each switch pair
                    isl_details[switch_pair] = switch_pair_isls[switch_pair]

    print(f"Found {len(switch_pair_isls)} switch pairs with ISLs:")
    for switch_pair, info in switch_pair_isls.items():
        print(f"  Switches {switch_pair[0]} and {switch_pair[1]}: {len(info['isls'])} ISLs with total capacity {info['total_capacity']}Gb")
        # Ensure all switch pairs are properly initialized in tracking dictionaries
        isl_traffic[switch_pair] = isl_traffic.get(switch_pair, 0)
        isl_details[switch_pair] = info
        
    # Debug the switch_pair_isls dictionary
    if len(switch_pair_isls) == 0:
        print("No ISL switch pairs were detected, but ISLs were found. This could be due to switch naming issues.")
        
        # List all detected E-ports
        print("\nDetected E-ports:")
        for wwpn, port in switches_to_use.items():
            if hasattr(port, 'switch_port_type') and 'E-PORT' in str(port.switch_port_type).upper():
                print(f"  Port: {wwpn}, Type: {port.switch_port_type}, Switch: {port.switch_name if hasattr(port, 'switch_name') else 'Unknown'}")
                
        # Try to create switch pairs from detected E-ports by sanitizing names
        print("\nAttempting to fix switch pair detection...")
        # Create a list of all detected E-ports for easier pairing
        e_ports = []
        for wwpn, switch_port in switches_to_use.items():
            if hasattr(switch_port, 'switch_port_type') and 'E-PORT' in str(switch_port.switch_port_type).upper() and hasattr(switch_port, 'connection'):
                e_ports.append((wwpn, switch_port))
        
        print(f"Found {len(e_ports)} E-ports to process")
        
        # Group E-ports by their switch name to identify unique switches
        switch_groups = {}
        for wwpn, switch_port in e_ports:
            if hasattr(switch_port, 'switch_name'):
                switch_name = str(switch_port.switch_name).strip()
                if switch_name not in switch_groups:
                    switch_groups[switch_name] = []
                switch_groups[switch_name].append((wwpn, switch_port))
        
        # For each E-port, try to create a switch pair with its connected port
        for wwpn, switch_port in e_ports:
            if hasattr(switch_port, 'connection'):
                # Get the connected port
                connected_port = get_port_by_wwpn(switch_port.connection)
                
                if connected_port and isinstance(connected_port, Switch):
                    # Create switch pair identifier
                    switch1_id = wwpn[:8]  # Use the first 8 chars of the WWPN as switch identifier
                    switch2_id = switch_port.connection[:8]  # Use the first 8 chars of the connected port's WWPN
                    
                    # Ensure we're not connecting to the same switch
                    if switch1_id == switch2_id:
                        continue
                    
                    # Create a tuple with the switch IDs sorted alphabetically
                    switch_pair = tuple(sorted([switch1_id, switch2_id]))
                    print(f"Fixed switch pair using WWPNs: {switch_pair}")
                    
                    # Initialize dictionaries for this switch pair if not already done
                    if switch_pair not in switch_pair_isls:
                        switch_pair_isls[switch_pair] = {
                            "isls": [],
                            "total_capacity": 0,
                            "traffic": 0,
                            "switch_names": switch_pair
                        }
                    if switch_pair not in isl_traffic:
                        isl_traffic[switch_pair] = 0
                        
                    # Add this ISL to the list if not already added
                    speed_value = int(''.join(filter(str.isdigit, switch_port.speed)))
                    isl_pair = tuple(sorted([wwpn, switch_port.connection]))
                    
                    # Check if we've already processed this ISL pair
                    already_added = False
                    for existing_isl in switch_pair_isls[switch_pair]["isls"]:
                        if existing_isl.get("isl_pair") == isl_pair:
                            already_added = True
                            break
                            
                    if not already_added:
                        # Add this ISL to the switch pair
                        isl_info = {
                            "isl_pair": isl_pair,
                            "representative_wwpn": isl_pair[0],
                            "speed": speed_value,
                            "switch_name": getattr(switch_port, 'switch_name', 'Unknown'),
                            "port_index": getattr(switch_port, 'port_index', 'Unknown'),
                            "port_type": getattr(switch_port, 'switch_port_type', 'Unknown'),
                            "remote_wwpn": switch_port.connection,
                            "remote_switch_name": getattr(connected_port, 'switch_name', 'Unknown')
                        }
                        
                        switch_pair_isls[switch_pair]["isls"].append(isl_info)
                        switch_pair_isls[switch_pair]["total_capacity"] += speed_value
                        
                        print(f"Added ISL {isl_pair} to switch pair {switch_pair}, capacity now: {switch_pair_isls[switch_pair]['total_capacity']}Gb")
                        
                        # Keep track of the details for each switch pair
                        isl_details[switch_pair] = switch_pair_isls[switch_pair]
    
    # If no ISLs were found, return appropriate message
    if len(switch_pair_isls) == 0:
        return {"status": "No traditional ISLs found - single switch fabric", "oversubscribed_isls": [], "total_nodes": len(node_traffic), "zones_analyzed": len(zones)}
    
    # Process zones for ISL traffic (traditional multi-switch analysis)
    for i, zone_members in enumerate(zones, 1):
        # Identify all initiators and targets in this zone
        initiators = []
        targets = []
        
        for wwpn in zone_members:
            # In test-path mode, we should use test_path_get_port_by_wwpn if available
            if 'test_path_mode' in globals() and test_path_mode and 'test_path_get_port_by_wwpn' in globals():
                port = test_path_get_port_by_wwpn(wwpn)
            else:
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
                # In test-path mode, we should use test_path_find_path_between_endpoints if available
                if 'test_path_mode' in globals() and test_path_mode and 'test_path_find_path_between_endpoints' in globals():
                    path = test_path_find_path_between_endpoints(initiator.wwpn, target.wwpn)
                else:
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
                    # In test-path mode, we should use test_path_get_port_by_wwpn if available
                    if 'test_path_mode' in globals() and test_path_mode and 'test_path_get_port_by_wwpn' in globals():
                        port_obj = test_path_get_port_by_wwpn(port_wwpn)
                    else:
                        port_obj = get_port_by_wwpn(port_wwpn)
                        
                    if port_obj and isinstance(port_obj, Switch):
                        switch_base = port_obj.wwpn[4:]
                        
                        # Find which switch pair this port belongs to
                        port_switch_name = str(port_obj.switch_name).strip() if hasattr(port_obj, 'switch_name') else None
                        
                        # Skip if we don't have a valid switch name
                        if not port_switch_name:
                            continue
                            
                        print(f"Checking if port {port_wwpn} on switch {port_switch_name} is part of an ISL")
                        
                        # Find if this port's switch is part of any switch pair
                        for switch_pair, pair_info in switch_pair_isls.items():
                            # Check if this switch name is part of the pair
                            if port_switch_name in switch_pair and switch_pair not in counted_switch_pairs:
                                # Add traffic to this switch pair (only once per switch pair per path)
                                if switch_pair not in isl_traffic:
                                    isl_traffic[switch_pair] = 0
                                isl_traffic[switch_pair] += connection_speed
                                print(f"  Added {connection_speed}Gb traffic to ISL between {switch_pair[0]} and {switch_pair[1]}")
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
        print(f"\nFound {analysis['total_isls']//2} ISLs in fabric.")
        
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

def show_system_information():
    """
    Display comprehensive system information for switches, storage nodes, and initiators.
    Shows release + model for switches, version for storage, and fw/dvr versions + model for initiators.
    """
    print("\n" + "="*80)
    print("                    SYSTEM INFORMATION")
    print("="*80)
    
    # Display Switch Information
    print("\n=== SWITCHES ===")
    if switch_nodes:
        for name, switch_node in switch_nodes.items():
            print(f"\nSwitch: {name}")
            print(f"  Model:           {switch_node.model}")
            print(f"  Release Version: {switch_node.release_version}")
            print(f"  Vendor:          {switch_node.vendor}")
            if switch_node.wwnn:
                print(f"  WWNN:            {switch_node.wwnn}")
    else:
        print("  No switch information available")
    
    # Display Storage Node Information
    print("\n=== STORAGE NODES ===")
    if target_nodes:
        for name, target_node in target_nodes.items():
            print(f"\nStorage Node: {name}")
            print(f"  Software Version: {target_node.sw_version}")
            
            # Count and display associated ports
            associated_ports = []
            for wwpn, target_port in target_ports.items():
                if isinstance(target_port, Target):
                    # Extract node number from port_id to match with node name
                    port_node_id = target_port.port_id.split(':')[0] if ':' in target_port.port_id else target_port.port_id
                    if f"node_{port_node_id}" == name:
                        associated_ports.append({
                            'wwpn': wwpn,
                            'port_id': target_port.port_id,
                            'speed': target_port.speed
                        })
            
            if associated_ports:
                print(f"  Ports ({len(associated_ports)}):")
                for port in associated_ports:
                    print(f"    - {port['wwpn']} ({port['port_id']}) - {port['speed']}")
            else:
                print("  No associated ports found")
    else:
        print("  No storage node information available")
    
    # Display Initiator Information
    print("\n=== INITIATORS ===")
    if initiator_nodes:
        for name, initiator_node in initiator_nodes.items():
            print(f"\nInitiator: {name}")
            print(f"  HBA Model:        {initiator_node.hba}")
            print(f"  Firmware Version: {initiator_node.fw_version}")
            print(f"  Driver Version:   {initiator_node.dvr_version}")
            
            # Display associated host ports
            print(f"  Host Ports:")
            for wwpn, host_port in host_ports.items():
                if isinstance(host_port, Initiator):
                    print(f"    - {wwpn} ({host_port.host_name}) - {host_port.speed}")
                    if host_port.connection:
                        print(f"      Connected to: {host_port.connection}")
                    else:
                        print(f"      Status: Not connected")
    else:
        print("  No initiator information available")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"Total Switches:      {len(switch_nodes)}")
    print(f"Total Storage Nodes: {len(target_nodes)}")
    print(f"Total Initiators:    {len(initiator_nodes)}")
    print(f"Total Target Ports:  {len(target_ports)}")
    print(f"Total Host Ports:    {len(host_ports)}")
    print(f"Total Switch Ports:  {len(switch_ports)}")
    print("="*80)

def display_target_arrays():
    """
    Display all TargetArray objects stored in the target_arrays dictionary.
    Shows detailed information about each storage array found in the fabric.
    """
    global target_arrays
    
    print("\n" + "="*70)
    print("                    TARGET ARRAYS")
    print("="*70)
    
    if not target_arrays:
        print("No target arrays found in the fabric.")
        return
    
    print(f"Total Target Arrays Found: {len(target_arrays)}")
    print("-" * 70)
    
    for i, (wwnn, target_array) in enumerate(target_arrays.items(), 1):
        print(f"\n{i}. Target Array:")
        print(f"   WWNN:          {target_array.wwnn}")
        print(f"   Name:          {target_array.name}")
        print(f"   Serial Number: {target_array.serial_number}")
        print(f"   Node Count:    {target_array.node_count}")

def build_host_mapping():
    """
    Build the host_mapping dictionary by iterating through all zones.
    Maps initiator WWPNs to arrays of target WWPNs they are zoned with.
    
    host_mapping format: {initiator_wwpn: [target_wwpn1, target_wwpn2, ...]}
    """
    global host_mapping, all_zones
    
    print("\n=== Building Host Mapping ===")
    
    # Clear existing host_mapping
    host_mapping.clear()
    
    # Iterate through all zones
    for zone_index, zone_members in enumerate(all_zones, 1):
        print(f"Processing Zone {zone_index}: {zone_members}")
        
        # Find all initiators and targets in this zone
        initiators_in_zone = []
        targets_in_zone = []
        
        for wwpn in zone_members:
            # Get the port object to determine its type
            port = get_port_by_wwpn(wwpn)
            
            if port:
                if isinstance(port, Initiator):
                    initiators_in_zone.append(wwpn)
                    print(f"  Found initiator: {wwpn}")
                elif isinstance(port, Target):
                    targets_in_zone.append(wwpn)
                    print(f"  Found target: {wwpn}")
            else:
                # Check in the individual port dictionaries if not found in indices
                if wwpn in host_ports:
                    initiators_in_zone.append(wwpn)
                    print(f"  Found initiator (from host_ports): {wwpn}")
                elif wwpn in target_ports:
                    targets_in_zone.append(wwpn)
                    print(f"  Found target (from target_ports): {wwpn}")
                else:
                    print(f"  Warning: WWPN {wwpn} not found in any port registry")
        
        # Map each initiator to all targets in this zone
        for initiator_wwpn in initiators_in_zone:
            # Initialize the initiator in host_mapping if not present
            if initiator_wwpn not in host_mapping:
                host_mapping[initiator_wwpn] = []
                print(f"  Created new entry for initiator {initiator_wwpn}")
            
            # Add all targets from this zone to the initiator's mapping
            for target_wwpn in targets_in_zone:
                if target_wwpn not in host_mapping[initiator_wwpn]:
                    host_mapping[initiator_wwpn].append(target_wwpn)
                    print(f"  Added target {target_wwpn} to initiator {initiator_wwpn}")
                else:
                    print(f"  Target {target_wwpn} already mapped to initiator {initiator_wwpn}")
    
    # Display the final host_mapping
    print(f"\n=== Host Mapping Summary ===")
    print(f"Total initiators mapped: {len(host_mapping)}")
    
    for initiator_wwpn, target_list in host_mapping.items():
        # Get initiator details for display
        initiator_port = get_port_by_wwpn(initiator_wwpn)
        initiator_name = "Unknown"
        if initiator_port and hasattr(initiator_port, 'host_name'):
            initiator_name = initiator_port.host_name
        
        print(f"\nInitiator: {initiator_wwpn} ({initiator_name})")
        print(f"  Mapped to {len(target_list)} target(s):")
        
        for target_wwpn in target_list:
            # Get target details for display
            target_port = get_port_by_wwpn(target_wwpn)
            target_name = "Unknown"
            if target_port and hasattr(target_port, 'array_name'):
                target_name = target_port.array_name
            
            print(f"    - {target_wwpn} ({target_name})")
    
    print(f"\nHost mapping completed. Total mappings: {len(host_mapping)}")
    return host_mapping

def display_host_mapping():
    """
    Display the host_mapping dictionary in a formatted way.
    """
    global host_mapping
    
    print("\n" + "="*70)
    print("                    HOST MAPPING")
    print("="*70)
    
    if not host_mapping:
        print("No host mappings found. Run build_host_mapping() first.")
        return
    
    print(f"Total Host Mappings: {len(host_mapping)}")
    print("-" * 70)
    
    for i, (initiator_wwpn, target_list) in enumerate(host_mapping.items(), 1):
        # Get initiator details
        initiator_port = get_port_by_wwpn(initiator_wwpn)
        initiator_info = "Unknown Host"
        if initiator_port:
            if hasattr(initiator_port, 'host_name'):
                initiator_info = initiator_port.host_name
            elif hasattr(initiator_port, 'port_id'):
                initiator_info = f"Port {initiator_port.port_id}"
        
        print(f"\n{i}. Initiator: {initiator_wwpn}")
        print(f"   Host: {initiator_info}")
        print(f"   Zoned to {len(target_list)} target(s):")
        
        for j, target_wwpn in enumerate(target_list, 1):
            # Get target details
            target_port = get_port_by_wwpn(target_wwpn)
            target_info = "Unknown Array"
            port_info = ""
            
            if target_port:
                if hasattr(target_port, 'array_name'):
                    target_info = target_port.array_name
                if hasattr(target_port, 'port_id'):
                    port_info = f" ({target_port.port_id})"
                if hasattr(target_port, 'speed'):
                    port_info += f" - {target_port.speed}"
            
            print(f"     {j}. {target_wwpn}{port_info}")
            print(f"        Array: {target_info}")
        
        print("-" * 50)
    
    print("="*70)

def check_host_node_connectivity(host_wwpn):
    """
    Check if a host (initiator) is connected to all nodes of target arrays.
    Ports with the same array_name are considered as one single connection to that node.
    
    Args:
        host_wwpn (str): The WWPN of the host/initiator to check
        
    Returns:
        dict: Dictionary containing connectivity analysis results
    """
    global host_mapping, target_arrays, target_ports
    
    print(f"\n=== Checking Host Node Connectivity for {host_wwpn} ===")
    
    # Check if host exists in host_mapping
    if host_wwpn not in host_mapping:
        print(f"Host {host_wwpn} not found in host_mapping dictionary")
        return {"error": "Host not found in mapping"}
        
    # Make sure host is properly connected to fabric
    host_port = get_port_by_wwpn(host_wwpn)
    if not host_port or not host_port.is_connected():
        print(f"Warning: Host {host_wwpn} is not connected to any switch")
        # Continue anyway since we're checking zoning, not physical connectivity
    
    # Get the target WWPNs this host is mapped to
    mapped_targets = host_mapping[host_wwpn]
    print(f"Host {host_wwpn} is mapped to {len(mapped_targets)} target(s):")
    for target in mapped_targets:
        print(f"  - {target}")
    
    # Group targets by array (based on array_name)
    arrays_connectivity = {}
    
    for target_wwpn in mapped_targets:
        # Get the target port object
        target_port = get_port_by_wwpn(target_wwpn)
        
        if target_port and hasattr(target_port, 'array_name'):
            array_name = target_port.array_name
            
            # Extract the base array name (remove node suffix)
            # For example: "S4256-node0" -> "S4256"
            base_array_name = array_name.split('-node')[0] if '-node' in array_name else array_name
            
            if base_array_name not in arrays_connectivity:
                arrays_connectivity[base_array_name] = {
                    'connected_nodes': set(),  # Use set to track unique node names
                    'connected_targets': [],   # Keep list for detailed reporting
                    'expected_nodes': 0,
                    'array_info': None
                }
            
            # Add the full array_name (including node) to the set of connected nodes
            arrays_connectivity[base_array_name]['connected_nodes'].add(array_name)
            
            # Also add to the detailed list for reporting
            arrays_connectivity[base_array_name]['connected_targets'].append({
                'wwpn': target_wwpn,
                'array_name': array_name,
                'port_id': getattr(target_port, 'port_id', 'Unknown')
            })
    
    # Get expected node counts from target_arrays
    for wwnn, target_array in target_arrays.items():
        array_name = target_array.name
        if array_name in arrays_connectivity:
            arrays_connectivity[array_name]['expected_nodes'] = target_array.node_count
            arrays_connectivity[array_name]['array_info'] = target_array
    
    # Analyze connectivity for each array
    connectivity_results = {}
    
    print(f"\n=== Connectivity Analysis ===")
    
    for array_name, connectivity_info in arrays_connectivity.items():
        # Count unique nodes (not ports)
        connected_node_count = len(connectivity_info['connected_nodes'])
        expected_count = connectivity_info['expected_nodes']
        
        is_fully_connected = connected_node_count == expected_count
        connectivity_percentage = (connected_node_count / expected_count * 100) if expected_count > 0 else 0
        
        connectivity_results[array_name] = {
            'array_name': array_name,
            'connected_nodes': connected_node_count,
            'expected_nodes': expected_count,
            'is_fully_connected': is_fully_connected,
            'connectivity_percentage': connectivity_percentage,
            'connected_targets': connectivity_info['connected_targets'],
            'connected_node_names': list(connectivity_info['connected_nodes']),
            'array_info': connectivity_info['array_info']
        }
        
        print(f"\nArray: {array_name}")
        print(f"  Expected nodes: {expected_count}")
        print(f"  Connected nodes: {connected_node_count}")
        print(f"  Connectivity: {connectivity_percentage:.1f}%")
        print(f"  Status: {'✓ FULLY CONNECTED' if is_fully_connected else '✗ PARTIAL CONNECTION'}")
        
        if not is_fully_connected:
            missing_nodes = expected_count - connected_node_count
            print(f"  Missing connections: {missing_nodes} node(s)")
        
        print(f"  Connected nodes: {list(connectivity_info['connected_nodes'])}")
        print(f"  Connected targets (by node):")
        
        # Group targets by node for better display
        targets_by_node = {}
        for target in connectivity_info['connected_targets']:
            node_name = target['array_name']
            if node_name not in targets_by_node:
                targets_by_node[node_name] = []
            targets_by_node[node_name].append(target)
        
        for node_name, targets in targets_by_node.items():
            print(f"    Node {node_name}: {len(targets)} port(s)")
            for target in targets:
                print(f"      - {target['wwpn']} (Port: {target['port_id']})")
    
    # Overall summary
    total_arrays = len(connectivity_results)
    fully_connected_arrays = sum(1 for result in connectivity_results.values() if result['is_fully_connected'])
    
    print(f"\n=== Overall Summary ===")
    print(f"Host: {host_wwpn}")
    print(f"Total arrays analyzed: {total_arrays}")
    print(f"Fully connected arrays: {fully_connected_arrays}")
    print(f"Partially connected arrays: {total_arrays - fully_connected_arrays}")
    
    if total_arrays > 0:
        overall_percentage = (fully_connected_arrays / total_arrays * 100)
        print(f"Overall connectivity: {overall_percentage:.1f}%")
    
    return {
        'host_wwpn': host_wwpn,
        'arrays': connectivity_results,
        'summary': {
            'total_arrays': total_arrays,
            'fully_connected': fully_connected_arrays,
            'partially_connected': total_arrays - fully_connected_arrays,
            'overall_percentage': overall_percentage if total_arrays > 0 else 0
        }
    }

def check_all_hosts_connectivity():
    """
    Check connectivity for all hosts in the host_mapping dictionary.
    """
    global host_mapping
    
    print("\n" + "="*80)
    print("                    ALL HOSTS CONNECTIVITY CHECK")
    print("="*80)
    
    if not host_mapping:
        print("No host mappings found. Run build_host_mapping() first.")
        return
    
    all_results = {}
    
    for host_wwpn in host_mapping.keys():
        print(f"\n{'-'*60}")
        result = check_host_node_connectivity(host_wwpn)
        all_results[host_wwpn] = result
    
    # Summary report
    print(f"\n" + "="*80)
    print("                    CONNECTIVITY SUMMARY REPORT")
    print("="*80)
    
    for host_wwpn, result in all_results.items():
        if 'error' not in result:
            summary = result['summary']
            print(f"\nHost: {host_wwpn}")
            print(f"  Arrays: {summary['total_arrays']}")
            print(f"  Fully Connected: {summary['fully_connected']}")
            print(f"  Partially Connected: {summary['partially_connected']}")
            print(f"  Overall: {summary['overall_percentage']:.1f}%")
    
    return all_results

def get_port_by_wwpn(wwpn):
    """
    Get port object by WWPN from all indexes and dictionaries.
    
    Args:
        wwpn (str): The WWPN to search for
        
    Returns:
        Port object or None if not found
    """
    # Check in the global index dictionaries first
    port = initiator_index.get(wwpn) or target_index.get(wwpn) or switch_index.get(wwpn)
    
    if port:
        return port
    
    # Check in the individual port dictionaries
    port = target_ports.get(wwpn) or host_ports.get(wwpn) or switch_ports.get(wwpn)
    
    return port


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
                show_system_information()
            elif choice == '2':
                interactive_check_connectivity()
            elif choice == '3':
                show_all_connections()
            elif choice == '4':
                display_isl_oversubscription_analysis()
            elif choice == '5':
                check_all_hosts_connectivity()
            elif choice == '6':
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
    print("1. Show system information")
    print("2. Check fabric connectivity")
    print("3. Show current topology")
    print("4. Check ISL oversubscription")
    print("5. Check host connectivity")
    print("6. Help")
    print("0. Exit")
    print("-" * 50)

if __name__ == "__main__":
    
    parse_showsys_output()
    print("Parsing showport, showhost, showportdev, and zoning output...")
    created_ports = parse_showport_output()

    # Parse node information and create TargetNode objects
    parse_node_information()

    # Establish switch connections
    establish_switch_connections()
    
    # Connect switches internally for proper path finding
    connect_switches_internally()

    # Debug zoning info
    debug_zoning_info()
    
    build_host_mapping()

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

