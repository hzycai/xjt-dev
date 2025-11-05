import uuid
import platform

def get_mac_address():
    """
    Get the MAC address of the local machine.
    
    Returns:
        str: MAC address in the format 'XX:XX:XX:XX:XX:XX'
    """
    mac = uuid.getnode()
    mac_address = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
    return mac_address

def get_mac_address_alternative():
    """
    Alternative method to get MAC address using uuid and formatting.
    
    Returns:
        str: MAC address in the format 'XX:XX:XX:XX:XX:XX'
    """
    mac = hex(uuid.getnode())[2:]
    # Ensure the MAC address is 12 characters long by padding with zeros if needed
    mac = mac.zfill(12)
    mac_address = ':'.join(mac[i:i+2] for i in range(0, 12, 2))
    return mac_address.upper()

if __name__ == "__main__":
    print("MAC Address:", get_mac_address())
    print("Alternative method:", get_mac_address_alternative())