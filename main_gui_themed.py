import configparser
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

def update_server(file_path, new_server_ip, branch_alias):
    # Check if the file exists
    if not os.path.exists(file_path):
        messagebox.showerror("Error", "The settings.ini file does not exist.")
        return
    
    # Create a ConfigParser object and read the file
    config = configparser.ConfigParser()
    config.read(file_path)
    
    # Check if the "Connection_Info" section exists
    if "Connection_Info" not in config:
        messagebox.showerror("Error", "The 'Connection_Info' section is missing in the settings.ini file.")
        return
    
    # Update the server IP
    config["Connection_Info"]["Server"] = new_server_ip
    
    # Write the changes back to the file
    with open(file_path, 'w') as configfile:
        config.write(configfile)
    
    # Display confirmation message
    messagebox.showinfo("Success", f"You are now connected to the {branch_alias} branch.")

def on_select_branch(branch_name, server_ip):
    # Path to the settings.ini file
    file_path = "settings.ini"
    
    # Update the server
    update_server(file_path, server_ip, branch_name)

def create_ui():
    # Create the main window
    root = tk.Tk()
    root.title("Branch Selector")
    root.geometry("400x300")
    root.resizable(False, False)
    
    # Add a themed style
    style = ttk.Style()
    style.theme_use("clam")  # Other themes: 'alt', 'default', 'classic'
    
    # Customize styles for labels and buttons
    style.configure("TLabel", font=("Arial", 14), padding=10)
    style.configure("TButton", font=("Arial", 12), padding=5)
    
    # Add a label
    ttk.Label(root, text="Select a Branch to Connect To:").pack(pady=20)
    
    # Branch options
    branches = [
        ("Wuse (192.168.0.5)", "Wuse", "192.168.0.5"),
        ("Asokoro (192.168.0.6)", "Asokoro", "192.168.0.6"),
        ("Maitama (192.168.0.7)", "Maitama", "192.168.0.7")
    ]
    
    # Add buttons for each branch
    for branch in branches:
        ttk.Button(
            root, 
            text=branch[0], 
            command=lambda b=branch: on_select_branch(b[1], b[2])
        ).pack(pady=10)
    
    # Run the application
    root.mainloop()

if __name__ == "__main__":
    create_ui()
