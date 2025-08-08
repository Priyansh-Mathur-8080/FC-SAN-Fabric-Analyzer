class TargetNode:
    """
    Represents a target node (storage array) in a Fibre Channel SAN network.
    """
    
    def __init__(self, name=None, sw_version=None):
        """
        Initialize a TargetNode instance.
        
        Args:
            name (str): Name of the target node/storage array
            sw_version (str): Software version of the storage array
        """
        self.name = name
        self.sw_version = sw_version
    
    def __str__(self):
        """String representation of the target node."""
        return f"TargetNode(name={self.name}, sw_version={self.sw_version})"
    
    def __repr__(self):
        """Detailed string representation of the target node."""
        return f"TargetNode(name='{self.name}', sw_version='{self.sw_version}')"


class SwitchNode:
    """
    Represents a switch node in a Fibre Channel SAN network.
    """
    
    def __init__(self, name=None, wwnn=None, release_version=None, model=None, port_count=None, vendor=None):
        """
        Initialize a SwitchNode instance.
        
        Args:
            name (str): Name of the switch
            wwnn (str): World Wide Node Name of the switch
            release_version (str): Firmware/software release version
            model (str): Switch model number
            port_count (int): Number of ports on the switch
            vendor (str): Switch vendor/manufacturer
        """
        self.name = name
        self.wwnn = wwnn
        self.release_version = release_version
        self.model = model
        self.port_count = port_count
        self.vendor = vendor
    
    def __str__(self):
        """String representation of the switch node."""
        return f"SwitchNode(name={self.name}, model={self.model}, vendor={self.vendor})"
    
    def __repr__(self):
        """Detailed string representation of the switch node."""
        return (f"SwitchNode(name='{self.name}', wwnn='{self.wwnn}', "
                f"release_version='{self.release_version}', model='{self.model}', "
                f"port_count={self.port_count}, vendor='{self.vendor}')")


class InitiatorNode:
    """
    Represents an initiator node (host server) in a Fibre Channel SAN network.
    """
    
    def __init__(self, name=None, hba=None, fw_version=None, dvr_version=None):
        """
        Initialize an InitiatorNode instance.
        
        Args:
            name (str): Name of the initiator node/host server
            hba (str): Host Bus Adapter model/type
            fw_version (str): Firmware version of the HBA
        """
        self.name = name
        self.hba = hba
        self.fw_version = fw_version
        self.dvr_version = dvr_version
    
    def __str__(self):
        """String representation of the initiator node."""
        return f"InitiatorNode(name={self.name}, hba={self.hba})"
    
    def __repr__(self):
        """Detailed string representation of the initiator node."""
        return f"InitiatorNode(name='{self.name}', hba='{self.hba}', fw_version='{self.fw_version}')"
    
class TargetArray:
    """
    Represents a target array (storage system) in a Fibre Channel SAN network.
    """
    
    def __init__(self, wwnn=None, name=None, node_count=0, serial_number=None):
        """
        Initialize a TargetArray instance.
        
        Args:
            wwnn (str): World Wide Node Name of the array
            name (str): Name/model of the storage array
            node_count (int): Number of nodes in the array
            serial_number (str): Serial number of the array
        """
        self.wwnn = wwnn
        self.name = name
        self.node_count = node_count
        self.serial_number = serial_number
        self.software_version = None  # Placeholder for software version, if needed
    
    def __str__(self):
        """String representation of the target array."""
        return f"TargetArray(name={self.name}, wwnn={self.wwnn}, nodes={self.node_count})"
    
    def __repr__(self):
        """Detailed string representation of the target array."""
        return (f"TargetArray(wwnn='{self.wwnn}', name='{self.name}', "
                f"node_count={self.node_count}, serial_number='{self.serial_number}')")