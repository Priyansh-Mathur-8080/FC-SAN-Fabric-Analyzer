class Port:
    """
    Represents a port in a Fibre Channel SAN network.
    """
    
    def __init__(self, wwpn=None, port_id=None, wwnn=None, port_type=None, 
                 if_switch_port=None, speed=None, connection=None):
        """
        Initialize a Port instance.
        
        Args:
            wwpn (str): World Wide Port Name
            port_id (str): Port identifier (formerly NSP - Node:Slot:Port)
            wwnn (str): World Wide Node Name
            port_type (str): Type of port - 'initiator', 'switch', or 'target'
            if_switch_port (str): Switch port type - 'e-port' if applicable
            speed (str): Port speed
            connection (str): Connected port WWPN
        """
        self.wwpn = wwpn
        self.port_id = port_id
        self.wwnn = wwnn
        self.port_type = port_type  # initiator/switch/target
        self.speed = speed
        self.connection = connection  # connected_port_wwpn
    
    def __str__(self):
        """String representation of the port."""
        return f"Port(wwpn={self.wwpn}, port_id={self.port_id}, type={self.port_type})"
    
    def __repr__(self):
        """Detailed string representation of the port."""
        return (f"Port(wwpn='{self.wwpn}', port_id='{self.port_id}', wwnn='{self.wwnn}', "
                f"port_type='{self.port_type}', if_switch_port='{self.if_switch_port}', "
                f"speed='{self.speed}', connection='{self.connection}')")
    
    def is_connected(self):
        """Check if the port is connected to another port."""
        return self.connection is not None
    
    def connect_to(self, other_port_wwpn):
        """Connect this port to another port."""
        self.connection = other_port_wwpn
    
    def disconnect(self):
        """Disconnect this port from any connected port."""
        self.connection = None


class Initiator(Port):
    """
    Represents an initiator port in a Fibre Channel SAN network.
    """
    
    def __init__(self, wwpn=None, port_id=None, wwnn=None, speed=None, 
                 connection=None, host_name=None):
        """
        Initialize an Initiator instance.
        
        Args:
            wwpn (str): World Wide Port Name
            port_id (str): Port identifier
            wwnn (str): World Wide Node Name
            speed (str): Port speed
            connection (str): Connected port WWPN
            host_name (str): Name of the host server
        """
        super().__init__(wwpn, port_id, wwnn, 'initiator', None, speed, connection)
        self.host_name = host_name
    
    def __str__(self):
        return f"Initiator(wwpn={self.wwpn}, host={self.host_name})"


class Target(Port):
    """
    Represents a target port in a Fibre Channel SAN network.
    """
    
    def __init__(self, wwpn=None, port_id=None, wwnn=None, speed=None, 
                 connection=None, array_name=None):
        """
        Initialize a Target instance.
        
        Args:
            wwpn (str): World Wide Port Name
            port_id (str): Port identifier
            wwnn (str): World Wide Node Name
            speed (str): Port speed
            connection (str): Connected port WWPN
            array_name (str): Name of the storage array
        """
        super().__init__(wwpn, port_id, wwnn, 'target', None, speed, connection)
        self.array_name = array_name
    
    def __str__(self):
        return f"Target(wwpn={self.wwpn}, array={self.array_name})"


class Switch(Port):
    """
    Represents a switch port in a Fibre Channel SAN network.
    """
    
    def __init__(self, wwpn=None, port_id=None, wwnn=None, speed=None, 
                 connection=None, switch_name=None, port_index=None, switch_port_type=None):
        """
        Initialize a Switch instance.
        
        Args:
            wwpn (str): World Wide Port Name
            port_id (str): Port identifier
            wwnn (str): World Wide Node Name
            speed (str): Port speed
            connection (str): Connected port WWPN
            switch_name (str): Name of the switch
            port_index (int): Physical port index on the switch
        """
        super().__init__(wwpn, port_id, wwnn, 'switch', None, speed, connection)
        self.switch_name = switch_name
        self.port_index = port_index
        self.switch_port_type = switch_port_type  # e-port, f-port, etc.

    
    def __str__(self):
        return f"Switch(wwpn={self.wwpn}, switch={self.switch_name}, port={self.port_index})"


# Global dictionaries to index ports by their WWPNs
initiator_index = {}  # WWPN -> Initiator object
target_index = {}     # WWPN -> Target object  
switch_index = {}     # WWPN -> Switch object

def register_port(port):
    """Register a port in the appropriate index based on its type (i/s/t)."""
    if isinstance(port, Initiator):
        initiator_index[port.wwpn] = port
        print(f"Registered Initiator: {port.wwpn}")
    elif isinstance(port, Target):
        target_index[port.wwpn] = port
        print(f"Registered Target: {port.wwpn}")
    elif isinstance(port, Switch):
        switch_index[port.wwpn] = port
        print(f"Registered Switch: {port.wwpn}")

def connect_ports(port1_wwpn, port2_wwpn):
    """Connect two ports by their WWPNs."""
    # Find the ports in all indexes
    port1 = None
    port2 = None
    
    # Look for port1
    if port1_wwpn in initiator_index:
        port1 = initiator_index[port1_wwpn]
    elif port1_wwpn in target_index:
        port1 = target_index[port1_wwpn]
    elif port1_wwpn in switch_index:
        port1 = switch_index[port1_wwpn]
    
    # Look for port2
    if port2_wwpn in initiator_index:
        port2 = initiator_index[port2_wwpn]
    elif port2_wwpn in target_index:
        port2 = target_index[port2_wwpn]
    elif port2_wwpn in switch_index:
        port2 = switch_index[port2_wwpn]
    
    if port1 and port2:
        port1.connect_to(port2_wwpn)
        port2.connect_to(port1_wwpn)
        print(f"Connected {port1.port_type} ({port1_wwpn}) to {port2.port_type} ({port2_wwpn})")
    else:
        print(f"Error: Could not find one or both ports - {port1_wwpn}, {port2_wwpn}")

def disconnect_ports(port1_wwpn, port2_wwpn):
    """Disconnect two ports by their WWPNs."""
    # Find the ports in all indexes
    port1 = None
    port2 = None
    
    # Look for port1
    if port1_wwpn in initiator_index:
        port1 = initiator_index[port1_wwpn]
    elif port1_wwpn in target_index:
        port1 = target_index[port1_wwpn]
    elif port1_wwpn in switch_index:
        port1 = switch_index[port1_wwpn]
    
    # Look for port2
    if port2_wwpn in initiator_index:
        port2 = initiator_index[port2_wwpn]
    elif port2_wwpn in target_index:
        port2 = target_index[port2_wwpn]
    elif port2_wwpn in switch_index:
        port2 = switch_index[port2_wwpn]
    
    if port1 and port2:
        port1.disconnect()
        port2.disconnect()
        print(f"Disconnected {port1.port_type} ({port1_wwpn}) from {port2.port_type} ({port2_wwpn})")
    else:
        print(f"Error: Could not find one or both ports - {port1_wwpn}, {port2_wwpn}")

