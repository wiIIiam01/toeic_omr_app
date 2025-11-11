import tkinter as tk
from gui import Layout

def run_omr_design():
    root = tk.Tk()
    app = Layout(root)
    root.mainloop()

if __name__ == "__main__":
    run_omr_design()