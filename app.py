import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from rx import Observable
from rx.operators import subscribe_on
from rx.scheduler import ThreadPoolScheduler
import os
import shutil
from typing import List, Optional
from background_remover import process_files 

class FileUploaderApp:
    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.title("File Uploader")
        self.root.geometry("700x700")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.thread_pool_scheduler = ThreadPoolScheduler()
        self.supported_file_types = (".png", ".jpeg", ".jpg", ".heic", )
        self.valid_files: List[str] = []
        self.current_zip_path: Optional[str] = None
        self.background_process: Optional[Observable] = None

        self.setup_ui()
        self.setup_bindings()

    def setup_ui(self) -> None:
        """Initialize all GUI components."""
        self.create_greeting_label()
        self.create_drop_frame()
        self.create_file_listbox()
        self.create_control_frame()
        self.create_download_section()

    def setup_bindings(self) -> None:
        """Set up event bindings."""
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self.handle_drop)

    def create_greeting_label(self) -> None:
        """Create the greeting text at the top."""
        self.greeting_label = tk.Label(
            self.root,
            text="Hi Y2K queen! 🙇🙇 Please upload the images you want to process,\n"
                 "and then wait a few minutes. You will receive a notification when your files are ready.",
            font=("Arial", 14),
            wraplength=500,
            justify="center"
        )
        self.greeting_label.place(relx=0.5, rely=0.1, anchor="center")

    def create_drop_frame(self) -> None:
        """Create the drag-and-drop area."""
        self.drop_frame = tk.Frame(self.root, bg="#f0f0f0", bd=2, relief="groove")
        self.drop_frame.place(relx=0.5, rely=0.3, anchor="center", width=500, height=150)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="Drag & Drop Files Here\nor",
            font=("Arial", 14),
            bg="#f0f0f0",
            fg="#333333"
        )
        self.drop_label.place(relx=0.5, rely=0.4, anchor="center")

        self.browse_button = tk.Button(
            self.drop_frame,
            text="Browse Files",
            font=("Arial", 12),
            bg="#0078d7",
            fg="white",
            command=self.browse_files
        )
        self.browse_button.place(relx=0.5, rely=0.7, anchor="center")

    def create_file_listbox(self) -> None:
        """Create the file list display."""
        self.file_listbox = tk.Listbox(
            self.root,
            font=("Arial", 12),
            bg="#ffffff",
            fg="#333333",
            selectbackground="#0078d7",
            selectforeground="white"
        )
        self.file_listbox.place(relx=0.5, rely=0.55, anchor="center", width=500, height=200)

    def create_control_frame(self) -> None:
        """Create control buttons and checkboxes."""
        self.control_frame = tk.Frame(self.root)
        self.control_frame.place(relx=0.5, rely=0.9, anchor="center")

        self.use_gpu = tk.BooleanVar(value=False)
        self.gpu_checkbox = tk.Checkbutton(
            self.control_frame,
            text="Use GPU",
            variable=self.use_gpu,
            font=("Arial", 12)
        )
        self.gpu_checkbox.pack(side=tk.LEFT, padx=10)

        self.submit_button = tk.Button(
            self.control_frame,
            text="Process Files",
            font=("Arial", 14),
            bg="#28a745",
            fg="white",
            command=self.process_files
        )
        self.submit_button.pack(side=tk.LEFT, padx=10)

        self.clear_button = tk.Button(
            self.control_frame,
            text="Clear All",
            font=("Arial", 14),
            bg="#dc3545",
            fg="white",
            command=self.reset
        )
        self.clear_button.pack(side=tk.LEFT, padx=10)

    def create_download_section(self) -> None:
        """Create the download section (initially hidden)."""
        self.download_frame = tk.Frame(self.root)
        self.download_button = tk.Button(
            self.download_frame,
            text="⬇️ Download Processed Files",
            font=("Arial", 14),
            bg="#0078d7",
            fg="white",
            command=self.download_files
        )
        self.download_button.pack(pady=10)
        self.download_frame.place(relx=0.5, rely=0.8, anchor="center")
        self.download_frame.place_forget()

    def set_ui_state(self, processing: bool = True) -> None:
        """Update UI elements to reflect processing state."""
        state = "disabled" if processing else "normal"
        self.browse_button.config(state=state)
        self.submit_button.config(state=state)
        self.gpu_checkbox.config(state=state)
        
        if processing:
            self.drop_frame.config(bg="#e0e0e0")
            self.drop_label.config(bg="#e0e0e0", fg="#999999")
            if not hasattr(self, 'disabled_overlay'):
                self.disabled_overlay = tk.Label(
                    self.drop_frame,
                    text="Upload in progress...",
                    font=("Arial", 18),
                    bg="#e0e0e0",
                    fg="#666666"
                )
                self.disabled_overlay.place(relx=0.5, rely=0.1, anchor="center")
        else:
            self.drop_frame.config(bg="#f0f0f0")
            self.drop_label.config(bg="#f0f0f0", fg="#333333")
            if hasattr(self, 'disabled_overlay'):
                self.disabled_overlay.destroy()

    def browse_files(self) -> None:
        """Open a file dialog to select files."""
        file_paths = filedialog.askopenfilenames(
            title="Select Files",
            filetypes=[("Image Files", "*.png *.jpeg *.jpg *.heic *.HEIC")]
        )
        if file_paths:
            self.add_files(file_paths)

    def handle_drop(self, event) -> None:
        """Handle files dropped into the drag-and-drop area."""
        file_paths = self.root.tk.splitlist(event.data)
        self.add_files(file_paths)

    def add_files(self, file_paths: List[str]) -> None:
        """Add valid files to the listbox."""
        existing_files = set(self.valid_files)
        for path in file_paths:
            clean_path = os.path.normpath(path)
            if clean_path.lower().endswith(self.supported_file_types):
                if clean_path not in existing_files:
                    self.valid_files.append(clean_path)
                    self.file_listbox.insert(tk.END, os.path.basename(clean_path))
            else:
                messagebox.showwarning(
                    "Unsupported File Type",
                    f"The file '{os.path.basename(clean_path)}' is not supported."
                )

    def process_files(self) -> None:
        """Initiate file processing with background threading."""
        if not self.valid_files:
            messagebox.showinfo("No Files", "Please select files first.")
            return

        self.set_ui_state(processing=True)
        messagebox.showinfo(
            "Processing Started",
            f"Processing {len(self.valid_files)} file(s). Please hold on to your tits..."
        )

        try:
            observable = process_files(self.valid_files, self.use_gpu.get())
            self.background_process = observable.pipe(
                subscribe_on(self.thread_pool_scheduler)
            ).subscribe(
                on_next=lambda path: self.root.after(0, self.enable_download, path),
                on_error=lambda e: self.root.after(0, self.handle_error, e),
                on_completed=lambda: self.root.after(0, self.set_ui_state, False)
            )
        except Exception as e:
            self.handle_error(e)

    def handle_error(self, error: Exception) -> None:
        """Handle errors during processing."""
        messagebox.showerror(
            "Processing Error",
            f"An error occurred: {str(error)}\nPlease try again."
        )
        self.reset()

    def enable_download(self, zip_path: str) -> None:
        """Enable download functionality after successful processing."""
        self.current_zip_path = zip_path
        self.download_frame.place(relx=0.5, rely=0.8, anchor="center")
        messagebox.showinfo(
            "Processing Complete",
            "Files ready! Click the download button to save."
        )

    def download_files(self) -> None:
        """Handle the file download process."""
        if not self.current_zip_path or not os.path.exists(self.current_zip_path.name):
            messagebox.showerror("Error", "No files available for download.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP Files", "*.zip")]
        )
        if not save_path:
            return  # User cancelled

        try:
            shutil.copy2(self.current_zip_path.name, save_path)
            messagebox.showinfo("Success", "Files downloaded successfully!")
            self.reset()
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to save files: {str(e)}")

    def reset(self) -> None:
        """Reset the application to its initial state."""
        if self.background_process:
            self.background_process.dispose()
        if self.current_zip_path and os.path.exists(self.current_zip_path.name):
            os.remove(self.current_zip_path.name)
        
        self.valid_files.clear()
        self.file_listbox.delete(0, tk.END)
        self.current_zip_path = None
        self.download_frame.place_forget()
        self.set_ui_state(processing=False)
        self.use_gpu.set(False)

    def on_close(self) -> None:
        """Handle window close event."""
        self.reset()
        self.root.destroy()

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = FileUploaderApp(root)
    root.mainloop()