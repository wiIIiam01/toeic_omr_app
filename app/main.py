import tkinter as tk
from gui import OMRLayoutDesign

def run_omr_design():
    root = tk.Tk()
    app = OMRLayoutDesign(root)
    root.mainloop()

if __name__ == "__main__":
    run_omr_design()