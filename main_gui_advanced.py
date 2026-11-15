import configparser
import os
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk


# Function to update the server in the settings file
def update_server(file_path, new_server_ip, branch_alias):
    """Updates the server IP in the settings.ini file."""
    if not os.path.exists(file_path):
        messagebox.showerror("Error", "The settings.ini file does not exist.")
        return

    config = configparser.ConfigParser()
    config.read(file_path)

    if "Connection_Info" not in config:
        messagebox.showerror(
            "Error",
            "The 'Connection_Info' section is missing in the settings.ini file.",
        )
        return

    config["Connection_Info"]["Server"] = new_server_ip

    with open(file_path, "w") as configfile:
        config.write(configfile)

    messagebox.showinfo(
        "Success", f"You are now connected to the {branch_alias} branch."
    )


# Function to handle branch selection
def on_select_branch(branch_name, server_ip):
    """Handles branch selection and updates the server."""
    file_path = "settings.ini"
    update_server(file_path, server_ip, branch_name)


# Function to toggle between light and dark themes
def toggle_dark_mode():
    """
    Toggles the application's theme between dark mode and light mode.
    """
    if dark_mode_var.get():  # If dark mode is active
        style.configure("TFrame", background="#2e2e2e")  # Dark mode background
        style.configure(
            "TLabel", background="#2e2e2e", foreground="#ffffff"
        )  # Text color
        style.configure(
            "TButton", background="#444444", foreground="#2e2e2e", bordercolor="#2e2e2e"
        )
        root.configure(bg="#2e2e2e")
        footer_label["foreground"] = "#ffffff"
        toggle_button["text"] = "🌙"  # Dark mode icon
    else:  # If light mode is active
        style.configure("TFrame", background="#f0f0f0")  # Light mode background
        style.configure(
            "TLabel", background="#f0f0f0", foreground="#000000"
        )  # Text color
        style.configure(
            "TButton", background="#ffffff", foreground="#000000", bordercolor="#000000"
        )
        root.configure(bg="#f0f0f0")
        footer_label["foreground"] = "#000000"
        toggle_button["text"] = "☀️"  # Light mode icon


# Create a themed root window
root = ThemedTk(theme="radiance")  # Default theme: light
root.title("Branch Selector")
root.geometry("600x400")
root.resizable(False, False)

# Custom style for modern appearance
style = ttk.Style(root)
style.configure("TButton", font=("Arial", 12, "bold"), padding=10)
style.configure("TLabel", font=("Arial", 14, "bold"), padding=5)
style.configure("TFrame", background="#f0f0f0")  # Default background for frames

# Background container frame
container = ttk.Frame(root, padding=20)
container.pack(fill="both", expand=True)

# Add a label for the title
title_label = ttk.Label(
    container,
    text="Select a Branch to Connect To",
    font=("Arial", 18, "bold"),
    anchor="center",
)
title_label.pack(pady=20)

# Branch options
branches = [
    ("Wuse (SERVER 1)", "Wuse", "192.168.0.5"),
    ("Asokoro (SERVER 2)", "Asokoro", "192.168.2.16"),
    ("YOBE (SERVER 3)", "Maitama", "192.168.0.7"),
]

# Add buttons for each branch
button_frame = ttk.Frame(container)
button_frame.pack(pady=10)

for branch in branches:
    branch_button = ttk.Button(
        button_frame,
        text=branch[0],
        command=lambda b=branch: on_select_branch(b[1], b[2]),
        style="TButton",
    )
    branch_button.pack(pady=10, fill="x", padx=50)

# Create a variable to track dark mode
dark_mode_var = tk.BooleanVar(value=False)

# Add a toggle button for dark mode
toggle_button = ttk.Button(
    root,
    text="☀️",  # Default state (light mode icon)
    command=lambda: (dark_mode_var.set(not dark_mode_var.get()), toggle_dark_mode()),
    style="TButton",
    width=3,
)
toggle_button.place(x=10, y=10)  # Position at the top-left corner

# Add a footer
footer_label = ttk.Label(
    container,
    text="Powered by Brickspoint Technologies",
    font=("Arial", 10, "italic"),
    anchor="center",
)
footer_label.pack(side="bottom", pady=10)

# Run the application
root.mainloop()
