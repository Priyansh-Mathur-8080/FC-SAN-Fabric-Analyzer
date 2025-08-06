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
    
    def __init__(self, name=None, hba=None, fw_version=None):
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
    
    def __str__(self):
        """String representation of the initiator node."""
        return f"InitiatorNode(name={self.name}, hba={self.hba})"
    
    def __repr__(self):
        """Detailed string representation of the initiator node."""
        return f"InitiatorNode(name='{self.name}', hba='{self.hba}', fw_version='{self.fw_version}')"