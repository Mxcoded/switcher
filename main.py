import configparser
import os

def update_server(file_path, new_server_ip, branch_alias):
    # Check if the file exists
    if not os.path.exists(file_path):
        print("The settings file does not exist.")
        return
    
    # Create a ConfigParser object and read the file
    config = configparser.ConfigParser()
    config.read(file_path)
    
    # Check if the "Connection_Info" section exists
    if "Connection_Info" not in config:
        print("The 'Connection_Info' section is missing in the settings file.")
        return
    
    # Update the server IP
    config["Connection_Info"]["Server"] = new_server_ip
    
    # Write the changes back to the file
    with open(file_path, 'w') as configfile:
        config.write(configfile)
    
    # Display confirmation message
    print(f"You are now connected to the {branch_alias} branch.")

# Main function to select the server and alias
def main():
    # Path to the settings.ini file
    file_path = "settings.ini"
    
    # Prompt the user for the new server IP and branch alias
    print("Select a branch to connect to:")
    print("1. Wuse (192.168.0.5)")
    print("2. Asokoro (192.168.0.6)")
    print("3. Maitama (192.168.0.7)")
    
    choice = input("Enter the number of your choice: ").strip()
    
    # Define server IP and branch alias based on user choice
    if choice == "1":
        new_server_ip = "192.168.0.5"
        branch_alias = "Wuse"
    elif choice == "2":
        new_server_ip = "192.168.0.6"
        branch_alias = "Asokoro"
    elif choice == "3":
        new_server_ip = "192.168.0.7"
        branch_alias = "Maitama"
    else:
        print("Invalid choice. Exiting program.")
        return
    
    # Call the function to update the server
    update_server(file_path, new_server_ip, branch_alias)

# Run the program
if __name__ == "__main__":
    main()
