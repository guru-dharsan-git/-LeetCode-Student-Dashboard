import tkinter as tk
from tkinter import ttk, filedialog, messagebox, PhotoImage
import pandas as pd
import httpx
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
import os
from datetime import datetime
import matplotlib
import webbrowser
matplotlib.use("TkAgg")

# Set modern font and style for plots
plt.rcParams['font.family'] = 'Arial'
plt.style.use('ggplot')

LEETCODE_API_URL = "https://leetcode.com/graphql"
USER_PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStats: submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
  }
}
"""

class LeetCodeDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("LeetCode Student Performance Dashboard")
        self.student_data = []
        self.displayed_data = []
        self.selected_students = []
        self.last_update_time = None
        
        # Set color scheme
        self.colors = {
            'bg': '#f5f5f7',
            'accent': '#3498db',
            'text': '#2c3e50',
            'easy': '#00b894',
            'medium': '#f39c12',
            'hard': '#e74c3c',
            'highlight': '#9b59b6',
            'secondary': '#34495e'
        }
        
        # Configure root window
        self.root.configure(bg=self.colors['bg'])
        self.configure_styles()
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self.root, bg=self.colors['bg'], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack canvas and scrollbar
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create inner frame for content
        self.inner_frame = ttk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.inner_frame, anchor=tk.NW)
        
        # Bind configuration events
        self.inner_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Bind mousewheel event
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Create widgets
        self.create_widgets()
        self.root.bind('<Control-s>', lambda event: self.export_data())
        
        # Set charts
        self.total_chart = None
        self.difficulty_chart = None
        self.comparison_chart = None
        self.progress_chart = None

    def _on_frame_configure(self, event=None):
        """Update scroll region when inner frame size changes"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Update inner frame width to match canvas"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_frame, width=canvas_width)

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        # Check if event occurs inside scrollable widgets
        widget = event.widget
        while widget:
            if isinstance(widget, (ttk.Treeview, tk.Text)):
                # Let scrollable widget handle the event
                return
            widget = widget.master
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def configure_styles(self):
        style = ttk.Style()
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        
        # Configure colors
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TNotebook', background=self.colors['bg'])
        style.configure('TNotebook.Tab', background=self.colors['bg'], padding=[12, 6])
        style.map('TNotebook.Tab', background=[('selected', self.colors['accent'])],
                  foreground=[('selected', 'white')])
        
        # Configure buttons
        style.configure('TButton', 
                         background=self.colors['accent'],
                         foreground='white',
                         font=('Arial', 10, 'bold'),
                         padding=8)
        style.map('TButton', 
                 background=[('active', self.colors['highlight'])],
                 relief=[('pressed', 'sunken')])
        
        # Secondary button style
        style.configure('Secondary.TButton', 
                         background=self.colors['secondary'],
                         foreground='white',
                         font=('Arial', 10),
                         padding=8)
        style.map('Secondary.TButton', 
                 background=[('active', '#4a6785')],
                 relief=[('pressed', 'sunken')])
        
        # Configure labels
        style.configure('TLabel', 
                         background=self.colors['bg'],
                         foreground=self.colors['text'],
                         font=('Arial', 10))
        
        style.configure('Header.TLabel', 
                         font=('Arial', 14, 'bold'),
                         foreground=self.colors['accent'],
                         background=self.colors['bg'])
        
        style.configure('Title.TLabel', 
                         font=('Arial', 18, 'bold'),
                         foreground=self.colors['text'],
                         background=self.colors['bg'])
        
        style.configure('Subtitle.TLabel', 
                         font=('Arial', 12, 'italic'),
                         foreground=self.colors['secondary'],
                         background=self.colors['bg'])
                         
        # Configure student info fields
        style.configure('Info.TLabel', 
                         font=('Arial', 11),
                         foreground=self.colors['text'],
                         background='white',
                         padding=10)
                         
        # Configure table
        style.configure('Treeview', 
                         rowheight=28,
                         font=('Arial', 10),
                         background='white',
                         fieldbackground='white')
        
        style.configure('Treeview.Heading', 
                         font=('Arial', 10, 'bold'),
                         foreground=self.colors['text'])
                         
        style.map('Treeview',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', 'white')])

    def create_widgets(self):
        # Create main notebook for tabs
        self.main_notebook = ttk.Notebook(self.inner_frame)
        self.main_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create main tabs
        self.dashboard_tab = ttk.Frame(self.main_notebook)
        self.about_tab = ttk.Frame(self.main_notebook)
        
        self.main_notebook.add(self.dashboard_tab, text="Dashboard")
        self.main_notebook.add(self.about_tab, text="About")
        
        # Setup Dashboard Tab
        self.setup_dashboard_tab()
        
        # Setup About Tab
        self.setup_about_tab()

    def show_invalid_profiles(self):
        """Display only students with invalid LeetCode profiles"""
        if not self.student_data:
            messagebox.showinfo("No Data", "Please upload student data first.")
            return

        # Filter the data to show only students with invalid profiles
        invalid_profiles = [
            student for student in self.student_data
            if student.get("leetcode_username") and not student.get("profile_found", False)
        ]

        if not invalid_profiles:
            messagebox.showinfo("No Invalid Profiles", "All students with LeetCode usernames have valid profiles.")
            return

        # Update displayed data and refresh
        self.displayed_data = invalid_profiles
        self.update_display()

        # Update status
        self.status.config(text=f"Showing {len(invalid_profiles)} students with invalid LeetCode profiles")


    def export_invalid_profiles(self):
        """Export a list of students with invalid LeetCode profiles to a CSV file"""
        if not self.student_data:
            messagebox.showinfo("No Data", "Please upload student data first.")
            return

        # Filter for invalid profiles
        invalid_profiles = [
            student for student in self.student_data
            if student.get("leetcode_username") and not student.get("profile_found", False)
        ]

        if not invalid_profiles:
            messagebox.showinfo("No Invalid Profiles", "All students with LeetCode usernames have valid profiles.")
            return

        # Let user choose where to save the file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Invalid LeetCode Profiles"
        )

        if not file_path:
            return  # User canceled

        try:
            # Convert to DataFrame and save
            df = pd.DataFrame(invalid_profiles)
            # Select relevant columns
            columns_to_export = ['name', 'roll_number', 'leetcode_username', 'email', 'phone']
            export_columns = [col for col in columns_to_export if col in df.columns]
            df[export_columns].to_csv(file_path, index=False)

            messagebox.showinfo("Export Successful", 
                               f"Exported {len(invalid_profiles)} students with invalid profiles to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export: {str(e)}")

    def export_data(self):
        """Export current displayed data to CSV/Excel file"""
        if not self.displayed_data:
            messagebox.showinfo("No Data", "No data to export")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx")],
            title="Save Student Data"
        )

        if not file_path:
            return  # User canceled

        try:
            df = pd.DataFrame(self.displayed_data)

            # Select and order relevant columns
            columns = [
                'name', 'roll_number', 'leetcode_username', 
                'problems_solved', 'easy_count', 'medium_count', 'hard_count',
                'email', 'phone', 'profile_found'
            ]

            # Create new DataFrame with selected columns
            export_df = df[columns]

            # Rename columns for better readability
            export_df = export_df.rename(columns={
                'leetcode_username': 'LeetCode Username',
                'problems_solved': 'Total Solved',
                'easy_count': 'Easy',
                'medium_count': 'Medium',
                'hard_count': 'Hard',
                'profile_found': 'Valid Profile'
            })

            if file_path.endswith('.csv'):
                export_df.to_csv(file_path, index=False)
            else:
                export_df.to_excel(file_path, index=False)

            messagebox.showinfo("Export Successful", 
                              f"Data exported successfully to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Export Failed", f"Error exporting data: {str(e)}")

    def setup_dashboard_tab(self):
        # Main container with padding
        container = ttk.Frame(self.dashboard_tab, padding=(20, 15))
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_frame = ttk.Frame(container)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(title_frame, text="LeetCode Student Performance Dashboard", style='Title.TLabel').pack(side=tk.LEFT)
        
        # Last update info
        self.update_label = ttk.Label(title_frame, text="", style='TLabel')
        self.update_label.pack(side=tk.RIGHT)
        
        # Top controls frame
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Upload Section
        upload_frame = ttk.LabelFrame(top_frame, text="Data Source", padding=(10, 5))
        upload_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ttk.Button(upload_frame, text="Upload CSV/Excel File", command=self.upload_file).pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(upload_frame, text="No file loaded", style='TLabel')
        self.file_label.pack(side=tk.LEFT, padx=10)
        # In the upload_frame section, after the upload button
        ttk.Button(upload_frame, text="Download Data", 
          command=self.export_data, style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        # Search Section
        search_frame = ttk.LabelFrame(top_frame, text="Search Students", padding=(10, 5))
        search_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Search", command=self.search_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Clear", command=self.clear_search, style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        # Add this to the upload_frame in setup_dashboard_tab where the other buttons are
        ttk.Button(upload_frame, text="Show Invalid Profiles", 
          command=self.show_invalid_profiles, style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(upload_frame, text="Export Invalid Profiles", 
          command=self.export_invalid_profiles, style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        # Add filter dropdown in search_frame
        filter_btn = ttk.Button(search_frame, text="Filters ▼", command=self.show_filter_menu)
        filter_btn.pack(side=tk.RIGHT, padx=5)
        self.filter_menu = tk.Menu(self.root, tearoff=0)
        self.filter_menu.add_command(label="All Students", command=self.clear_search)
        self.filter_menu.add_command(label="Valid Profiles Only", command=self.show_valid_profiles)
        self.filter_menu.add_command(label="Invalid Profiles Only", command=self.show_invalid_profiles)
        self.filter_menu.add_separator()
        self.filter_menu.add_command(label="Top 10 Students", command=self.show_top_students)
        self.filter_menu.add_command(label="Zero Solved Problems", command=self.show_zero_solved)
        # Main content area with table and charts
        content_frame = ttk.Frame(container)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left side - table + student comparison + student details
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10), pady=(0, 10))
        
        # Split left frame vertically
        top_left = ttk.Frame(left_frame)
        top_left.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        bottom_left = ttk.Frame(left_frame)
        bottom_left.pack(fill=tk.X)
        
        # Table frame in top left
        table_container = ttk.LabelFrame(top_left, text="Student Data", padding=(10, 5))
        table_container.pack(fill=tk.BOTH, expand=True)
        self.create_table(table_container)
        
        # Student details frame in bottom left
        student_details = ttk.LabelFrame(bottom_left, text="Student Details", padding=(10, 5))
        student_details.pack(fill=tk.X, pady=(0, 10))
        self.create_student_details(student_details)
        
        # Comparison selection frame
        comparison_frame = ttk.LabelFrame(bottom_left, text="Student Comparison", padding=(10, 5))
        comparison_frame.pack(fill=tk.X)
        
        ttk.Label(comparison_frame, text="Select students for comparison:").pack(anchor=tk.W, pady=(0, 5))
        
        # Buttons for comparison
        btn_frame = ttk.Frame(comparison_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Compare Selected", 
                  command=self.compare_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear Selection", 
                  command=self.clear_selection, style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        
        # Right side - charts
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Notebook for charts
        self.chart_notebook = ttk.Notebook(right_frame)
        self.chart_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add tabs for different charts
        self.total_tab = ttk.Frame(self.chart_notebook)
        self.difficulty_tab = ttk.Frame(self.chart_notebook)
        self.comparison_tab = ttk.Frame(self.chart_notebook)
        self.progress_tab = ttk.Frame(self.chart_notebook)
        
        self.chart_notebook.add(self.total_tab, text="Total Problems")
        self.chart_notebook.add(self.difficulty_tab, text="Difficulty Breakdown")
        self.chart_notebook.add(self.comparison_tab, text="Student Comparison")
        self.chart_notebook.add(self.progress_tab, text="Class Distribution")
        
        # Status Bar with progress
        status_frame = ttk.Frame(container)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.progress = ttk.Progressbar(status_frame, mode='determinate')
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.status = ttk.Label(status_frame, text="Ready", relief=tk.SUNKEN, padding=(5, 2))
        self.status.pack(side=tk.RIGHT, fill=tk.X)
    def _handle_text_scroll(self, event):
        """Handle Text widget scrolling"""
        event.widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    def setup_about_tab(self):
        # Create content with padding
        container = ttk.Frame(self.about_tab, padding=(30, 20))
        container.pack(fill=tk.BOTH, expand=True)
        
        # App logo/title
        title_frame = ttk.Frame(container)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(title_frame, text="LeetCode Student Performance Dashboard", 
                style="Title.TLabel").pack(anchor=tk.CENTER)
        ttk.Label(title_frame, text="Track and visualize student coding progress", 
                style="Subtitle.TLabel").pack(anchor=tk.CENTER, pady=(5, 0))
        
        # Version info
        version_frame = ttk.Frame(container)
        version_frame.pack(fill=tk.X, pady=(0, 30))
        ttk.Label(version_frame, text="Version 1.1.0", font=('Arial', 10)).pack(anchor=tk.CENTER)
        
        # Creator info
        creator_frame = ttk.LabelFrame(container, text="Created By", padding=(15, 10))
        creator_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(creator_frame, text="Gurudharsan T", 
                font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        
        # Contact info with clickable links
        contact_frame = ttk.Frame(creator_frame)
        contact_frame.pack(fill=tk.X, pady=(10, 0))
        
        # WhatsApp
        whatsapp_frame = ttk.Frame(contact_frame)
        whatsapp_frame.pack(fill=tk.X, pady=5)
        ttk.Label(whatsapp_frame, text="WhatsApp:", 
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        whatsapp_link = ttk.Label(whatsapp_frame, text="+91 9488587594", 
                              foreground="blue", cursor="hand2", font=('Arial', 10, 'underline'))
        whatsapp_link.pack(side=tk.LEFT)
        whatsapp_link.bind("<Button-1>", lambda e: webbrowser.open("https://wa.me/919488587594"))
        
        # Gmail
        gmail_frame = ttk.Frame(contact_frame)
        gmail_frame.pack(fill=tk.X, pady=5)
        ttk.Label(gmail_frame, text="Email:", 
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        gmail_link = ttk.Label(gmail_frame, text="gurudharsan.work@gmail.com", 
                           foreground="blue", cursor="hand2", font=('Arial', 10, 'underline'))
        gmail_link.pack(side=tk.LEFT)
        gmail_link.bind("<Button-1>", lambda e: webbrowser.open("mailto:gurudharsan.work@gmail.com"))
        
        # Description
        desc_frame = ttk.LabelFrame(container, text="About This Application", padding=(15, 10))
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        description = (
            "This dashboard helps educators and mentors track student performance on LeetCode coding platform. "
            "It provides visual insights into problem-solving patterns, difficulty distribution, and peer comparison.\n\n"
            "Features:\n"
            "• Import student data from Excel/CSV files\n"
            "• Automatically fetch LeetCode profiles and solving statistics\n"
            "• Visual charts for student performance analysis\n"
            "• Student comparison tools\n"
            "• Search and filter functionality\n\n"
            "For support or feature requests, please contact the developer using the information above."
        )
        
        desc_text = tk.Text(desc_frame, wrap=tk.WORD, height=12, width=60, 
                          font=('Arial', 11), bd=0, padx=5, pady=5)
        desc_text.bind("<MouseWheel>", self._handle_text_scroll)
        desc_text.pack(fill=tk.BOTH, expand=True)
        desc_text.insert(tk.END, description)
        desc_text.config(state=tk.DISABLED)  # Make read-only

    def sort_treeview(self, column):
        """Sort treeview content when a column header is clicked"""
        column_index = {"Name": "name", 
                        "LeetCode Username": "leetcode_username", 
                        "Total Solved": "problems_solved", 
                        "Easy": "easy_count", 
                        "Medium": "medium_count", 
                        "Hard": "hard_count",
                        "Profile": "profile_found"}

        # Get the current sort direction if it exists, else set to 'asc'
        if hasattr(self, 'sort_direction') and self.sort_direction == 'asc':
            self.sort_direction = 'desc'
        else:
            self.sort_direction = 'asc'

        # Store current sort column
        self.sort_column = column

        # Sort the displayed data
        self.displayed_data = sorted(
            self.displayed_data,
            key=lambda x: (x.get(column_index[column], "") is None, 
                          x.get(column_index[column], "")),
            reverse=(self.sort_direction == 'desc')
        )

        # Update arrow in column header
        for col in self.tree["columns"]:
            if col != column:
                self.tree.heading(col, text=col.replace(" ▲", "").replace(" ▼", ""))

        # Update text in the sorted column
        self.tree.heading(column, 
                         text=column.replace(" ▲", "").replace(" ▼", "") + 
                              (" ▲" if self.sort_direction == 'asc' else " ▼"))

        # Update display
        self.update_display()   
    def _handle_treeview_scroll(self, event):
        """Handle Treeview-specific scrolling"""
        self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"  # Prevent event propagation
    def create_table(self, parent):
        # Create a frame for the table with scrollbars
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Define columns
        columns = ("Name", "LeetCode Username", "Total Solved", "Easy", "Medium", "Hard", "Profile")

        # Create treeview
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.bind("<MouseWheel>", self._handle_treeview_scroll)  # Add this line
        # Add scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Place scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Configure column headings
        for col in columns:
            self.tree.heading(col, text=col, anchor=tk.CENTER, 
                             command=lambda c=col: self.sort_treeview(c))

        # Set column widths
        self.tree.column("Name", width=150, anchor=tk.W)
        self.tree.column("LeetCode Username", width=120, anchor=tk.W)
        self.tree.column("Total Solved", width=90, anchor=tk.CENTER)
        self.tree.column("Easy", width=70, anchor=tk.CENTER)
        self.tree.column("Medium", width=70, anchor=tk.CENTER)
        self.tree.column("Hard", width=70, anchor=tk.CENTER)
        self.tree.column("Profile", width=70, anchor=tk.CENTER)

        # Configure grid weights
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bind selection event for comparison and details display
        self.tree.bind("<<TreeviewSelect>>", self.on_student_select)
 
    def create_student_details(self, parent):
        details_frame = ttk.Frame(parent)
        details_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
        
        # Create info fields with labels
        fields_frame = ttk.Frame(details_frame)
        fields_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Student Name
        name_frame = ttk.Frame(fields_frame)
        name_frame.pack(fill=tk.X, pady=2)
        ttk.Label(name_frame, text="Name:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        ttk.Label(name_frame, textvariable=self.name_var, style="Info.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # LeetCode Username
        username_frame = ttk.Frame(fields_frame)
        username_frame.pack(fill=tk.X, pady=2)
        ttk.Label(username_frame, text="LeetCode:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.username_var = tk.StringVar()
        ttk.Label(username_frame, textvariable=self.username_var, style="Info.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Roll Number
        roll_frame = ttk.Frame(fields_frame)
        roll_frame.pack(fill=tk.X, pady=2)
        ttk.Label(roll_frame, text="Roll Number:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.roll_var = tk.StringVar()
        ttk.Label(roll_frame, textvariable=self.roll_var, style="Info.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Email
        email_frame = ttk.Frame(fields_frame)
        email_frame.pack(fill=tk.X, pady=2)
        ttk.Label(email_frame, text="Email:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.email_var = tk.StringVar()
        ttk.Label(email_frame, textvariable=self.email_var, style="Info.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Phone
        phone_frame = ttk.Frame(fields_frame)
        phone_frame.pack(fill=tk.X, pady=2)
        ttk.Label(phone_frame, text="Phone:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.phone_var = tk.StringVar()
        ttk.Label(phone_frame, textvariable=self.phone_var, style="Info.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # LeetCode Stats
        stats_frame = ttk.Frame(fields_frame)
        stats_frame.pack(fill=tk.X, pady=2)
        ttk.Label(stats_frame, text="LeetCode Stats:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.stats_var = tk.StringVar()
        ttk.Label(stats_frame, textvariable=self.stats_var, style="Info.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Initialize with empty values
        self.clear_student_details()

    def clear_student_details(self):
        self.name_var.set("No student selected")
        self.username_var.set("-")
        self.roll_var.set("-")
        self.email_var.set("-")
        self.phone_var.set("-")
        self.stats_var.set("-")

    def update_student_details(self, student):
        if student:
            self.name_var.set(student.get("name", "Unknown"))
            self.username_var.set(student.get("leetcode_username", "-"))
            self.roll_var.set(student.get("roll_number", "-"))
            self.email_var.set(student.get("email", "-"))
            self.phone_var.set(student.get("phone", "-"))
            
            # Format LeetCode stats
            if student.get("profile_found", False):
                stats = f"Total: {student.get('problems_solved', 0)} | Easy: {student.get('easy_count', 0)} | "
                stats += f"Medium: {student.get('medium_count', 0)} | Hard: {student.get('hard_count', 0)}"
                self.stats_var.set(stats)
            else:
                self.stats_var.set("Profile not found")
        else:
            self.clear_student_details()

    def upload_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV/Excel Files", "*.csv *.xls *.xlsx")],
            title="Select Student Data File"
        )
        if file_path:
            self.status.config(text="Processing file...")
            self.file_label.config(text=os.path.basename(file_path))
            self.progress['value'] = 0
            Thread(target=self.process_file, args=(file_path,), daemon=True).start()

    def process_file(self, file_path):
        try:
            self.root.after(0, lambda: self.progress.config(value=10))
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            self.root.after(0, lambda: self.progress.config(value=20))
            
            required_columns = ["name", "leetcode_username"]
            optional_columns = ["roll_number", "email", "phone"]
            
            if not all(col in df.columns for col in required_columns):
                self.root.after(0, self.show_error, "Missing required columns: name or leetcode_username")
                return

            # Convert DataFrame to dictionary records
            self.student_data = df.to_dict('records')
            
            # Add missing columns as empty values
            for student in self.student_data:
                for col in optional_columns:
                    if col not in student:
                        student[col] = ""
            
            total_students = len(self.student_data)
            valid_students = sum(1 for s in self.student_data if s.get("leetcode_username"))
            
            self.root.after(0, lambda: self.status.config(text=f"Fetching LeetCode data for {valid_students} students..."))
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                student_indices = []
                
                for i, student in enumerate(self.student_data):
                    if student.get("leetcode_username"):
                        futures.append(executor.submit(
                            self.fetch_leetcode_data,
                            student["leetcode_username"]
                        ))
                        student_indices.append(i)
                
                for i, future in enumerate(futures):
                    # Update progress
                    progress_value = 20 + int(70 * (i+1) / len(futures))
                    self.root.after(0, lambda val=progress_value: self.progress.config(value=val))
                    
                    result = future.result()
                    idx = student_indices[i]
                    username = self.student_data[idx]["leetcode_username"]
                    
                    if result["found"]:
                        self.student_data[idx].update({
                            "problems_solved": result["total_solved"],
                            "easy_count": result["easy"],
                            "medium_count": result["medium"],
                            "hard_count": result["hard"],
                            "profile_found": True
                        })
                    else:
                        self.student_data[idx].update({
                            "problems_solved": 0,
                            "easy_count": 0,
                            "medium_count": 0,
                            "hard_count": 0,
                            "profile_found": False
                        })

            # Record update time
            self.last_update_time = datetime.now()
            self.displayed_data = self.student_data.copy()
            self.root.after(0, lambda: self.progress.config(value=100))
            self.root.after(0, self.update_display)
            
        except Exception as e:
            self.root.after(0, self.show_error, f"Error processing file: {str(e)}")
            self.root.after(0, lambda: self.progress.config(value=0))

    def fetch_leetcode_data(self, username):
        try:
            response = httpx.post(
                LEETCODE_API_URL,
                json={"query": USER_PROFILE_QUERY, "variables": {"username": username}},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("matchedUser"):
                    submissions = data["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]
                    easy = next((i["count"] for i in submissions if i["difficulty"] == "Easy"), 0)
                    medium = next((i["count"] for i in submissions if i["difficulty"] == "Medium"), 0)
                    hard = next((i["count"] for i in submissions if i["difficulty"] == "Hard"), 0)
                    # Calculate total correctly by adding the individual difficulty counts
                    total = easy + medium + hard
                    
                    return {
                        "found": True,
                        "total_solved": total,
                        "easy": easy,
                        "medium": medium,
                        "hard": hard
                    }
            return {"found": False, "total_solved": 0, "easy": 0, "medium": 0, "hard": 0}
        except Exception as e:
            return {"found": False, "total_solved": 0, "easy": 0, "medium": 0, "hard": 0}

    def update_display(self):
        self.status.config(text="Updating display...")
        
        # Update last refresh time
        if self.last_update_time:
            time_str = self.last_update_time.strftime("%b %d, %Y %I:%M %p")
            self.update_label.config(text=f"Last updated: {time_str}")
        
        # Clear table
        self.tree.delete(*self.tree.get_children())
        
        # Insert data
        for student in self.displayed_data:
            self.tree.insert("", tk.END, values=(
                student.get("name", ""),
                student.get("leetcode_username", ""),
                student.get("problems_solved", 0),
                student.get("easy_count", 0),
                student.get("medium_count", 0),
                student.get("hard_count", 0),
                "✅" if student.get("profile_found") else "❌"
            ))
        
        # Clear student details
        self.clear_student_details()
        
        # Update charts
        self.update_charts()
        self.status.config(text=f"Ready - {len(self.displayed_data)} students displayed")

    def update_charts(self):
        # Update Total Problems Chart
        self.update_total_chart()
        
        # Update Difficulty Breakdown Chart
        self.update_difficulty_chart()
        
        # Update Class Distribution
        self.update_progress_chart()
        
        # Clear comparison chart if no selection
        if not self.selected_students:
            self.update_comparison_chart([])

    def update_total_chart(self):
        # Clear previous chart
        for widget in self.total_tab.winfo_children():
            widget.destroy()
        
        # Create figure frame
        chart_frame = ttk.Frame(self.total_tab)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
        fig = Figure(figsize=(8, 5), dpi=100, facecolor=self.colors['bg'])
        ax = fig.add_subplot(111)
        
        # Get top 15 students by problems solved
        sorted_data = sorted(self.displayed_data, key=lambda x: x.get("problems_solved", 0), reverse=True)[:15]
        
        if not sorted_data:
            # No data - show placeholder
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            names = [s.get("name", "Unknown") for s in sorted_data]
            values = [s.get("problems_solved", 0) for s in sorted_data]
            
            # Create horizontal bar chart
            bars = ax.barh(names, values, color=self.colors['accent'], alpha=0.8)
            
            # Add values to end of bars
# Add values to end of bars
            for bar in bars:
                width = bar.get_width()
                ax.text(width + 1, bar.get_y() + bar.get_height()/2, 
                       f'{int(width)}', va='center', fontsize=9)
            
            # Style the chart
            ax.set_title('Top Students by Problems Solved', fontsize=14, pad=15)
            ax.set_xlabel('Number of Problems', fontsize=12)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Adjust layout
            plt.tight_layout()
        
        # Add the plot to the tab
        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.total_chart = canvas

    def update_difficulty_chart(self):
        # Clear previous chart
        for widget in self.difficulty_tab.winfo_children():
            widget.destroy()
        
        # Create figure frame
        chart_frame = ttk.Frame(self.difficulty_tab)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        fig = Figure(figsize=(8, 5), dpi=100, facecolor=self.colors['bg'])
        ax = fig.add_subplot(111)
        
        # Get top 10 students by total solved
        sorted_data = sorted(self.displayed_data, key=lambda x: x.get("problems_solved", 0), reverse=True)[:10]
        
        if not sorted_data:
            # No data - show placeholder
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            names = [s.get("name", "Unknown") for s in sorted_data]
            easy = [s.get("easy_count", 0) for s in sorted_data]
            medium = [s.get("medium_count", 0) for s in sorted_data]
            hard = [s.get("hard_count", 0) for s in sorted_data]
            
            # Create stacked bar chart
            width = 0.7
            ax.bar(names, easy, width, label='Easy', color=self.colors['easy'])
            ax.bar(names, medium, width, bottom=easy, label='Medium', color=self.colors['medium'])
            
            # Calculate the bottom position for hard problems
            bottom_hard = [e + m for e, m in zip(easy, medium)]
            ax.bar(names, hard, width, bottom=bottom_hard, label='Hard', color=self.colors['hard'])
            
            # Style the chart
            ax.set_title('Problem Difficulty Breakdown', fontsize=14, pad=15)
            ax.set_ylabel('Number of Problems', fontsize=12)
            ax.legend()
            
            # Rotate x-labels for better readability
            plt.xticks(rotation=45, ha='right')
            
            # Remove top and right spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Adjust layout
            plt.tight_layout()
        
        # Add the plot to the tab
        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.difficulty_chart = canvas

    def update_comparison_chart(self, students):
        # Clear previous chart
        for widget in self.comparison_tab.winfo_children():
            widget.destroy()
        
        if not students:
            # No students selected - show message
            ttk.Label(self.comparison_tab, 
                    text="Select students from the table for comparison", 
                    style='Header.TLabel').pack(expand=True)
            return
        
        # Create figure frame
        chart_frame = ttk.Frame(self.comparison_tab)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        fig = Figure(figsize=(8, 5), dpi=100, facecolor=self.colors['bg'])
        ax = fig.add_subplot(111)
        
        # Set width of bars
        width = 0.25
        multiplier = 0
        
        # X-axis positions
        x = np.arange(3)  # easy, medium, hard categories
        
        # For each student
        for student in students:
            counts = [
                student.get("easy_count", 0),
                student.get("medium_count", 0),
                student.get("hard_count", 0)
            ]
            
            offset = width * multiplier
            rects = ax.bar(x + offset, counts, width, label=student.get("name", "Unknown"))
            
            # Add counts above bars
            for rect in rects:
                height = rect.get_height()
                ax.annotate(f'{int(height)}',
                          xy=(rect.get_x() + rect.get_width() / 2, height),
                          xytext=(0, 3),  # 3 points vertical offset
                          textcoords="offset points",
                          ha='center', va='bottom', fontsize=9)
            
            multiplier += 1
        
        # Add labels
        ax.set_title('Student Comparison by Problem Difficulty', fontsize=14, pad=15)
        ax.set_xticks(x + width, ['Easy', 'Medium', 'Hard'])
        ax.set_ylabel('Number of Problems', fontsize=12)
        ax.legend(loc='best')
        
        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Adjust layout
        plt.tight_layout()
        
        # Add the plot to the tab
        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.comparison_chart = canvas

    def update_progress_chart(self):
        # Clear previous chart
        for widget in self.progress_tab.winfo_children():
            widget.destroy()
        
        # Create figure frame
        chart_frame = ttk.Frame(self.progress_tab)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        fig = Figure(figsize=(8, 5), dpi=100, facecolor=self.colors['bg'])
        ax = fig.add_subplot(111)
        
        if not self.displayed_data:
            # No data - show placeholder
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            # Group students by problems solved ranges
            ranges = [(0, 0), (1, 25), (26, 50), (51, 100), (101, 200), (201, 300), (301, float('inf'))]
            labels = ['0', '1-25', '26-50', '51-100', '101-200', '201-300', '301+']
            
            # Count students in each range
            counts = [0] * len(ranges)
            for student in self.displayed_data:
                problems = student.get("problems_solved", 0)
                for i, (min_val, max_val) in enumerate(ranges):
                    if min_val <= problems <= max_val:
                        counts[i] += 1
                        break
            
            # Create bar chart
            bars = ax.bar(labels, counts, color=self.colors['accent'], alpha=0.8)
            
            # Add counts above bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, height + 0.1,
                          f'{int(height)}', ha='center', va='bottom', fontsize=10)
            
            # Style the chart
            ax.set_title('Class Distribution by Problems Solved', fontsize=14, pad=15)
            ax.set_xlabel('Number of Problems', fontsize=12)
            ax.set_ylabel('Number of Students', fontsize=12)
            
            # Remove top and right spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Adjust layout
            plt.tight_layout()
        
        # Add the plot to the tab
        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.progress_chart = canvas

    def search_data(self):
        query = self.search_var.get().lower().strip()
        if query:
            self.displayed_data = [
                student for student in self.student_data
                if query in str(student.get("name", "")).lower() or
                   query in str(student.get("leetcode_username", "")).lower() or
                   query in str(student.get("roll_number", "")).lower() or
                   query in str(student.get("email", "")).lower()
            ]
        else:
            self.displayed_data = self.student_data.copy()
        
        self.update_display()

    def clear_search(self):
        self.search_var.set("")
        self.displayed_data = self.student_data.copy()
        self.update_display()

    def on_student_select(self, event):
        # Get selected items
        selected_items = self.tree.selection()
        
        if selected_items:
            # Get the first selected student to display details
            selected_id = selected_items[0]
            selected_idx = self.tree.index(selected_id)
            
            if 0 <= selected_idx < len(self.displayed_data):
                self.update_student_details(self.displayed_data[selected_idx])
            
            # Update selected students list for comparison
            self.selected_students = []
            for item in selected_items:
                idx = self.tree.index(item)
                if 0 <= idx < len(self.displayed_data):
                    self.selected_students.append(self.displayed_data[idx])
        else:
            self.clear_student_details()
            self.selected_students = []

    def compare_selected(self):
        if len(self.selected_students) < 1:
            messagebox.showinfo("Selection Required", "Please select at least one student to compare.")
            return
        elif len(self.selected_students) > 5:
            messagebox.showinfo("Too Many Selected", "Please select no more than 5 students for comparison.")
            return
        
        self.update_comparison_chart(self.selected_students)
        # Switch to comparison tab
        self.chart_notebook.select(self.comparison_tab)

    def clear_selection(self):
        self.tree.selection_remove(self.tree.selection())
        self.clear_student_details()
        self.selected_students = []
        self.update_comparison_chart([])

    def show_error(self, message):
        messagebox.showerror("Error", message)
        self.status.config(text="Error")

    def show_filter_menu(self, event=None):
        """Display the filter dropdown menu"""
        # Get the filter button's position
        widgets = [w for w in self.root.winfo_children() if isinstance(w, ttk.Button) and w.cget('text') == "Filters ▼"]
        if widgets:
            x = widgets[0].winfo_rootx()
            y = widgets[0].winfo_rooty() + widgets[0].winfo_height()
            self.filter_menu.post(x, y)
        else:
            # Fallback if button not found
            self.filter_menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def show_valid_profiles(self):
        """Display only students with valid LeetCode profiles"""
        if not self.student_data:
            messagebox.showinfo("No Data", "Please upload student data first.")
            return

        valid_profiles = [
            student for student in self.student_data
            if student.get("profile_found", False)
        ]

        if not valid_profiles:
            messagebox.showinfo("No Valid Profiles", "No students with valid LeetCode profiles found.")
            return

        self.displayed_data = valid_profiles
        self.update_display()
        self.status.config(text=f"Showing {len(valid_profiles)} students with valid LeetCode profiles")

    def show_top_students(self):
        """Display top 10 students by problems solved"""
        if not self.student_data:
            messagebox.showinfo("No Data", "Please upload student data first.")
            return

        top_students = sorted(
            self.student_data, 
            key=lambda x: x.get("problems_solved", 0), 
            reverse=True
        )[:10]

        self.displayed_data = top_students
        self.update_display()
        self.status.config(text=f"Showing top 10 students by problems solved")

    def show_zero_solved(self):
        """Display students who haven't solved any problems"""
        if not self.student_data:
            messagebox.showinfo("No Data", "Please upload student data first.")
            return

        zero_solved = [
            student for student in self.student_data
            if student.get("problems_solved", 0) == 0 and student.get("leetcode_username")
        ]

        if not zero_solved:
            messagebox.showinfo("No Data", "No students with zero solved problems found.")
            return

        self.displayed_data = zero_solved
        self.update_display()
        self.status.config(text=f"Showing {len(zero_solved)} students with zero solved problems")


def main():
    root = tk.Tk()
    root.geometry("1280x720")
    root.minsize(1000, 650)
    root.configure(bg='#f5f5f7')
    app = LeetCodeDashboard(root)
    root.mainloop()

if __name__ == "__main__":
    main()
