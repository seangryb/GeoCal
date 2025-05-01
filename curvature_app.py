import sys
import json
import os
import ast # Import ast for literal_eval
import inspect # Import inspect for dynamic loading
import base64
import shutil # For finding latex executable and which
import tempfile # For sympy.preview temporary file and TinyTeX rendering
import subprocess # For running latex/dvipng directly

#import sympy
from sympy import symbols, latex, Symbol
from sympy.parsing.sympy_parser import parse_expr
from sympy.tensor.array import ImmutableDenseNDimArray # Import for export
from sympy.matrices.dense import DenseMatrix # Import for type checking
from einsteinpy.symbolic import (
    MetricTensor, RicciTensor, RicciScalar, RiemannCurvatureTensor,
    ChristoffelSymbols, EinsteinTensor, WeylTensor
)
import einsteinpy.symbolic.predefined as predefined_metrics

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QCheckBox, QLineEdit, QFormLayout, QMessageBox, QGroupBox, QLabel,
    QGridLayout, QSplitter, QTextEdit, QFileDialog, QMenuBar, QInputDialog
)
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtCore import Qt, QSettings

BUILTIN_METRICS = {}
EXCLUDED_CLASSES = {'MetricTensor', 'BaseMetricTensor'}

for name, obj in inspect.getmembers(predefined_metrics):
    if inspect.isfunction(obj) and name not in EXCLUDED_CLASSES:
        try:
            instance = obj()
            if hasattr(instance, 'tensor') and hasattr(instance, 'syms'):
                BUILTIN_METRICS[name] = obj
        except TypeError:
            pass
        except Exception:
            pass

CUSTOM_METRICS_FILE = "custom_metrics.json"

ORGANIZATION_NAME = "GeoCal"
APPLICATION_NAME = "GeoCal"

# Rendering Modes - Simplified
RENDER_TINYTEX = "LaTeX"
RENDER_STRING = "Plane Text"
RENDERING_MODES = [RENDER_TINYTEX, RENDER_STRING]

class CurvatureApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APPLICATION_NAME)
        self.setGeometry(100, 100, 1200, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Load settings
        self.settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        default_dir = os.path.dirname(os.path.abspath(__file__)) # Default to script directory
        self.custom_metrics_dir = self.settings.value("customMetricsDirectory", default_dir)
        # Load rendering mode, default to TinyTeX
        self.rendering_mode = self.settings.value("renderingMode", RENDER_TINYTEX)
        if self.rendering_mode not in RENDERING_MODES: # Ensure saved value is valid
            self.rendering_mode = RENDER_TINYTEX

        self.custom_metrics = self.load_custom_metrics()
        self.metric_matrix_inputs = []
        self.delete_custom_button = None
        self.results_display = QTextEdit() # Always use QTextEdit now
        self.results_display.setReadOnly(True)
        self.current_metric = None
        self.computed_results = {}
        self.latex_render_failed_once = False # Flag for ANY latex rendering errors (TinyTeX or System)

        self._setup_menus() # Setup menus
        self.setup_ui()

        # --- Post-UI Setup Warnings ---
        # Warning if TinyTeX needed but not found
        if self.rendering_mode == RENDER_TINYTEX and not self._get_tinytex_bin_path():
             print("Warning: TinyTeX installation not found or incomplete in './TinyTeX'. TinyTeX rendering will fail.")

    def _get_tinytex_bin_path(self):
        """Checks for a relative './TinyTeX' directory and returns the platform-specific bin path if latex/dvipng exist."""
        base_path = os.path.dirname(os.path.abspath(__file__)) # Path of the script
        tinytex_root = os.path.join(base_path, "TinyTeX")

        if not os.path.isdir(tinytex_root):
            return None

        platform = sys.platform
        bin_subdir = ""
        latex_exe = "latex"
        dvipng_exe = "dvipng"

        if platform == "win32":
            bin_subdir = "windows" # TinyTeX convention
            latex_exe += ".exe"
            dvipng_exe += ".exe"
        elif platform == "darwin":
            bin_subdir = "universal-darwin" # Common convention
        elif platform.startswith("linux"):
            bin_subdir = "x86_64-linux"
        else:
            print(f"Warning: Unsupported platform '{platform}' for TinyTeX auto-detection.")
            return None

        bin_path = os.path.join(tinytex_root, "bin", bin_subdir)

        if not os.path.isdir(bin_path):
            return None

        latex_full_path = os.path.join(bin_path, latex_exe)
        dvipng_full_path = os.path.join(bin_path, dvipng_exe)

        if os.path.isfile(latex_full_path) and os.path.isfile(dvipng_full_path):
            return bin_path
        else:
            return None

    def _setup_menus(self):
        """Creates the application menus."""
        menu_bar = self.menuBar()
        options_menu = menu_bar.addMenu("&Options")

        # --- Rendering Mode ---
        render_menu = options_menu.addMenu("Rendering Mode")
        self.render_mode_group = QActionGroup(self)
        self.render_mode_group.setExclusive(True)

        for mode in RENDERING_MODES:
            action = QAction(mode, self, checkable=True)
            action.triggered.connect(lambda checked, m=mode: self._update_rendering_mode(m))
            if mode == self.rendering_mode:
                action.setChecked(True)
            render_menu.addAction(action)
            self.render_mode_group.addAction(action)

    def _update_rendering_mode(self, mode):
        """Updates the rendering mode based on menu selection."""
        if mode != self.rendering_mode:
            print(f"Rendering mode changed to: {mode}")
            self.rendering_mode = mode
            self.settings.setValue("renderingMode", self.rendering_mode)
            # Reset failure flag when mode changes, maybe it works now
            self.latex_render_failed_once = False
            # Optional: Trigger a re-render of the current view if results exist
            if self.computed_results:
                 print("Re-rendering results with new mode...")
                 html_content = self.generate_results_html(self.computed_results)
                 self.results_display.setHtml(html_content)
            elif self.current_metric:
                 print("Re-rendering metric preview with new mode...")
                 self.display_metric_preview(self.current_metric)

    def _render_latex_to_png(self, expr):
        """
        Generates PNG using LaTeX. Tries bundled TinyTeX first, then system latex/dvipng.
        Returns base64 URI or None on failure.
        """
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp()
            # Minimal article class, rely on dvipng -T tight for cropping
            latex_code = (
                "\\documentclass{article}\n"
                "\\usepackage{amsmath}\n"
                "\\usepackage{amssymb}\n"
                "\\usepackage{amsfonts}\n"
                "\\usepackage{lmodern}\n"
                "\\pagestyle{empty}\n" # Remove page numbers
                "\\begin{document}\n"
                # Use displaymath environment
                "\\begin{displaymath}\n"
                "{\\large\n"
                f"{latex(expr)}\n"
                "}\n"
                "\\end{displaymath}\n"
                "\\end{document}\n"
            )
            tex_filename = os.path.join(temp_dir, "expr.tex")
            dvi_filename = os.path.join(temp_dir, "expr.dvi")
            png_filename = os.path.join(temp_dir, "expr.png")

            with open(tex_filename, "w", encoding="utf-8") as f:
                f.write(latex_code)

            # --- Attempt 1: TinyTeX ---
            tinytex_bin_path = self._get_tinytex_bin_path()
            latex_exe = None
            dvipng_exe = None
            render_method = "None"

            if tinytex_bin_path:
                latex_exe_try = os.path.join(tinytex_bin_path, "latex.exe" if sys.platform == "win32" else "latex")
                dvipng_exe_try = os.path.join(tinytex_bin_path, "dvipng.exe" if sys.platform == "win32" else "dvipng")
                if os.path.isfile(latex_exe_try) and os.path.isfile(dvipng_exe_try):
                    latex_exe = latex_exe_try
                    dvipng_exe = dvipng_exe_try
                    render_method = "TinyTeX"
                    print(f"Attempting rendering with {render_method}...")
                else:
                    print("TinyTeX path found, but latex/dvipng executables missing within.")
            else:
                print("TinyTeX path not found.")

            # --- Attempt 2: System LaTeX (if TinyTeX failed or wasn't found/valid) ---
            if not latex_exe:
                print("Checking for system LaTeX...")
                latex_exe_sys = shutil.which("latex")
                dvipng_exe_sys = shutil.which("dvipng")
                if latex_exe_sys and dvipng_exe_sys:
                    latex_exe = latex_exe_sys
                    dvipng_exe = dvipng_exe_sys
                    render_method = "System LaTeX"
                    print(f"Attempting rendering with {render_method}...")
                else:
                    print("System latex or dvipng not found in PATH.")

            # --- Execute Rendering (if an executable pair was found) ---
            if latex_exe and dvipng_exe:
                print(f"Running {render_method} latex in {temp_dir}...")
                latex_result = subprocess.run(
                    [latex_exe, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", temp_dir, tex_filename],
                    capture_output=True, text=True, check=False,
                    cwd=temp_dir # Ensure cwd is set for latex
                )
                if latex_result.returncode != 0 or not os.path.exists(dvi_filename):
                    print(f"{render_method} latex failed (Code: {latex_result.returncode}).")
                    print("--- LaTeX Stdout ---")
                    print(latex_result.stdout)
                    print("--- LaTeX Stderr ---")
                    print(latex_result.stderr)
                    # Don't set failure flag here yet, just signal failure for this attempt
                    latex_exe = None # Mark as failed
                else:
                    print(f"Running {render_method} dvipng in {temp_dir}...")
                    dvipng_result = subprocess.run(
                        [dvipng_exe, "-T", "tight", "-D", "150", "-bg", "Transparent", "-o", png_filename, dvi_filename],
                         capture_output=True, text=True, check=False,
                         cwd=temp_dir # Ensure cwd is set for dvipng
                    )

                    if dvipng_result.returncode != 0 or not os.path.exists(png_filename) or os.path.getsize(png_filename) == 0:
                        print(f"{render_method} dvipng failed (Code: {dvipng_result.returncode}).")
                        print("Stderr:", dvipng_result.stderr)
                        latex_exe = None # Mark as failed
                    else:
                        # Success!
                        with open(png_filename, "rb") as f:
                            png_bytes = f.read()
                        base64_png = base64.b64encode(png_bytes).decode('utf-8')
                        print(f"PNG generated successfully using {render_method}.")
                        # self.latex_render_failed_once = False # Reset flag on success
                        return f"data:image/png;base64,{base64_png}"

            # --- If both attempts failed or were skipped ---
            if not self.latex_render_failed_once:
                print("LaTeX rendering failed (tried TinyTeX and/or System LaTeX). Will fall back to string.")
                self.latex_render_failed_once = True
            return None

        except Exception as e:
            print(f"Error during LaTeX rendering process: {e}")
            if not self.latex_render_failed_once:
                self.latex_render_failed_once = True
            return None
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    print(f"Warning: Could not remove temporary directory {temp_dir}: {e}")

    def _generate_png_data_uri(self, expr):
        """Generates a base64 encoded PNG data URI using LaTeX (TinyTeX or System). Returns None on failure or if String mode is selected."""
        if expr is None:
            return None

        png_uri = None

        # Only try LaTeX if that mode is selected
        if self.rendering_mode == RENDER_TINYTEX:
            print("Rendering Mode: LaTeX (TinyTeX/System)")
            png_uri = self._render_latex_to_png(expr) # Use the new function
            if png_uri is None:
                 # Message printed inside _render_latex_to_png if it fails
                 pass

        elif self.rendering_mode == RENDER_STRING:
            print("Rendering Mode: String (Skipping PNG generation)")
            return None # Explicitly return None for String mode

        # Return URI if successful, otherwise None
        if png_uri:
            return png_uri
        else:
            # Failure message already printed by _render_latex_to_png if attempted
            # print("PNG generation failed or skipped for the selected mode.")
            return None

    def load_custom_metrics(self):
        try:
            full_path = os.path.join(self.custom_metrics_dir, CUSTOM_METRICS_FILE)
            with open(full_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Load Error", f"Could not decode {full_path}. Starting with empty custom metrics.")
            return {}

    def save_custom_metrics(self):
        full_path = os.path.join(self.custom_metrics_dir, CUSTOM_METRICS_FILE)
        try:
            with open(full_path, 'w') as f:
                json.dump(self.custom_metrics, f, indent=4)
        except IOError as e:
            QMessageBox.critical(self, "Save Error", f"Could not save custom metrics to {full_path}: {e}")

    def setup_ui(self):
        main_layout = QHBoxLayout(self.central_widget)

        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setSpacing(10)

        metric_group = QGroupBox("Metric Selection")
        metric_layout = QVBoxLayout()

        self.metric_combo = QComboBox()
        self.metric_combo.addItem("Select Metric...")
        self.metric_combo.addItems(["--- Custom ---"] + sorted(list(self.custom_metrics.keys())))
        self.metric_combo.addItem("Add New...")
        self.metric_combo.currentIndexChanged.connect(self.handle_metric_selection)
        metric_layout.addWidget(self.metric_combo)

        self.custom_metric_group = QGroupBox("Define / Edit Custom Metric")
        self.custom_metric_layout = QFormLayout()
        self.custom_metric_layout.FieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.custom_metric_name_input = QLineEdit()
        self.custom_metric_coords_input = QLineEdit()
        self.custom_metric_coords_input.setPlaceholderText("(e.g., t, r, theta, phi)")
        self.custom_metric_coords_input.textChanged.connect(self.update_metric_grid_state)

        self.metric_matrix_grid_layout = QGridLayout()
        self.metric_matrix_inputs = []
        for i in range(4):
            row_inputs = []
            for j in range(4):
                line_edit = QLineEdit()
                line_edit.setPlaceholderText(f"g_{i}{j}")
                self.metric_matrix_grid_layout.addWidget(line_edit, i, j)
                row_inputs.append(line_edit)
            self.metric_matrix_inputs.append(row_inputs)

        self.custom_metric_layout.addRow("Name:", self.custom_metric_name_input)
        self.custom_metric_layout.addRow("Coordinates:", self.custom_metric_coords_input)
        self.custom_metric_layout.addRow(QLabel("Metric components (g_ab):"))
        self.custom_metric_layout.addRow(self.metric_matrix_grid_layout)

        button_layout = QHBoxLayout()
        save_update_button = QPushButton("Save / Update")
        save_update_button.clicked.connect(self.save_or_update_custom_metric)
        self.delete_custom_button = QPushButton("Delete")
        self.delete_custom_button.clicked.connect(self.delete_custom_metric)
        self.delete_custom_button.setEnabled(False)
        button_layout.addWidget(save_update_button)
        button_layout.addWidget(self.delete_custom_button)
        self.custom_metric_layout.addRow(button_layout)

        self.custom_metric_group.setLayout(self.custom_metric_layout)
        self.custom_metric_group.setVisible(False)
        metric_layout.addWidget(self.custom_metric_group)

        metric_group.setLayout(metric_layout)
        left_panel_layout.addWidget(metric_group)

        # --- Custom Metrics Directory ---
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Custom Metrics Directory:")
        self.custom_dir_input = QLineEdit(self.custom_metrics_dir)
        self.custom_dir_input.setReadOnly(True) # Display only
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_custom_metrics_dir)
        metric_layout.addWidget(dir_label)
        dir_layout.addWidget(self.custom_dir_input)
        dir_layout.addWidget(browse_button)
        metric_layout.addLayout(dir_layout)
        # --- End Custom Metrics Directory ---

        # Add Built-in metrics after custom section in UI setup
        self.metric_combo.addItems(["--- Built-in ---"] + sorted(list(BUILTIN_METRICS.keys())))

        curvature_group = QGroupBox("Curvature Quantities")
        curvature_layout = QVBoxLayout()
        self.christoffel_check = QCheckBox("Christoffel Symbols (Γ^a_{bc})")
        self.riemann_check = QCheckBox("Riemann Tensor (R^a_{bcd})")
        self.ricci_tensor_check = QCheckBox("Ricci Tensor (R_{ab})")
        self.ricci_scalar_check = QCheckBox("Ricci Scalar (R)")
        self.einstein_tensor_check = QCheckBox("Einstein Tensor (G_{ab})")
        self.weyl_tensor_check = QCheckBox("Weyl Tensor (C^a_{bcd})") # Note: Weyl is 4D only
        curvature_layout.addWidget(self.christoffel_check)
        curvature_layout.addWidget(self.riemann_check)
        curvature_layout.addWidget(self.ricci_tensor_check)
        curvature_layout.addWidget(self.ricci_scalar_check)
        curvature_layout.addWidget(self.einstein_tensor_check)
        curvature_layout.addWidget(self.weyl_tensor_check)
        curvature_group.setLayout(curvature_layout)
        left_panel_layout.addWidget(curvature_group)

        self.compute_button = QPushButton("Compute Curvature")
        self.compute_button.clicked.connect(self.compute_curvature)
        left_panel_layout.addWidget(self.compute_button)

        # --- Export Button ---
        export_layout = QHBoxLayout() # Layout for export buttons
        self.export_latex_button = QPushButton("Export .tex")
        self.export_latex_button.clicked.connect(self.export_latex)
        self.export_latex_button.setEnabled(False) # Initially disabled
        export_layout.addWidget(self.export_latex_button)

        self.export_python_button = QPushButton("Export .py")
        self.export_python_button.clicked.connect(self.export_python)
        self.export_python_button.setEnabled(False) # Initially disabled
        export_layout.addWidget(self.export_python_button)

        left_panel_layout.addLayout(export_layout) # Add the button layout
        # --- End Export Button ---

        left_panel_layout.addStretch()

        # Right panel for results display - Always QTextEdit now
        self.results_display.setHtml("<p>Select a metric and compute curvature to see results here.</p>")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel_widget)
        splitter.addWidget(self.results_display) # Add the QTextEdit
        splitter.setSizes([350, 650])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        self.update_metric_grid_state()

    def browse_custom_metrics_dir(self):
        """Opens a dialog to select the custom metrics directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Custom Metrics Directory",
            self.custom_metrics_dir  # Start browsing from the current directory
        )
        if directory and directory != self.custom_metrics_dir:
            reply = QMessageBox.question(self, 'Change Directory',
                                         f"Load custom metrics from '{directory}'?\nUnsaved changes to the current set will be lost.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.custom_metrics_dir = directory
                self.custom_dir_input.setText(directory)
                self.settings.setValue("customMetricsDirectory", directory) # Save setting

                # Reload metrics and update UI
                self.custom_metrics = self.load_custom_metrics()
                self.update_metric_combo_box()
                self.metric_combo.setCurrentIndex(0) # Reset selection

    def update_metric_combo_box(self):
        """Updates the custom metrics listed in the combo box."""
        self.metric_combo.currentIndexChanged.disconnect(self.handle_metric_selection) # Disconnect to avoid signals
        # Clear existing custom metrics (items between "--- Custom ---" and "Add New...")
        while self.metric_combo.itemText(1) != "Add New...":
            self.metric_combo.removeItem(1)
        # Add current custom metrics sorted
        self.metric_combo.insertItems(1, sorted(list(self.custom_metrics.keys())))
        self.metric_combo.currentIndexChanged.connect(self.handle_metric_selection) # Reconnect

    def update_metric_grid_state(self):
        coords_str = self.custom_metric_coords_input.text().strip()
        dim = 0
        if coords_str:
            try:
                raw_coords = symbols(coords_str)
                coords = raw_coords if isinstance(raw_coords, tuple) else (raw_coords,)
                if all(isinstance(c, Symbol) for c in coords):
                    dim = len(coords)
                else:
                    dim = 0
            except (SyntaxError, TypeError, ValueError):
                dim = 0

        dim = max(0, min(dim, 4)) # Ensure dim is between 0 and 4

        for i in range(4):
            for j in range(4):
                line_edit = self.metric_matrix_inputs[i][j]
                # Disconnect any previous lambda connection to avoid duplicates or stale references
                try:
                    line_edit.textChanged.disconnect()
                except (TypeError, RuntimeError): # No connection or already disconnected
                    pass

                is_active = (i < dim and j < dim)
                is_upper_triangle = (i <= j)
                is_editable = is_active and is_upper_triangle

                line_edit.setEnabled(is_editable)

                if is_editable:
                    line_edit.setStyleSheet("") # Reset style
                    # If it's an upper off-diagonal element, connect its signal
                    if i < j:
                        # Use a lambda with default arguments to capture current i, j
                        line_edit.textChanged.connect(lambda text, row=i, col=j: self._update_symmetric_component(text, row, col))
                else: # Lower triangle or outside dimension
                    line_edit.setStyleSheet("background-color: #f0f0f0;")
                    if not is_active: # Outside dimension, clear it
                        line_edit.clear()
                    # Lower triangle (i > j and is_active) will be updated by the signal from g_ji

    def _update_symmetric_component(self, text, i, j):
        """Slot to update g_ji when g_ij changes (i < j)."""
        # Check bounds and ensure the target component exists and is within the current dimension
        coords_str = self.custom_metric_coords_input.text().strip()
        dim = 0
        if coords_str:
            try:
                raw_coords = symbols(coords_str)
                coords = raw_coords if isinstance(raw_coords, tuple) else (raw_coords,)
                if all(isinstance(c, Symbol) for c in coords):
                    dim = len(coords)
            except (SyntaxError, TypeError, ValueError):
                pass # dim remains 0

        dim = max(0, min(dim, 4))

        if i < j and j < dim and i < dim: # Ensure indices are valid and within current dimension
            target_line_edit = self.metric_matrix_inputs[j][i]
            # Check if the target is disabled (it should be, as it's lower triangle)
            if not target_line_edit.isEnabled():
                 # Block signals to prevent potential loops if we ever connected signals to lower triangle
                target_line_edit.blockSignals(True)
                target_line_edit.setText(text)
                target_line_edit.blockSignals(False)

    def handle_metric_selection(self, index):
        selection = self.metric_combo.itemText(index)
        is_defining_new = (selection == "Add New...")
        is_custom_selected = selection in self.custom_metrics
        self.custom_metric_group.setVisible(is_defining_new or is_custom_selected)

        self.delete_custom_button.setEnabled(is_custom_selected)
        self.custom_metric_name_input.setReadOnly(is_custom_selected)

        # Clear previous results and preview
        self.computed_results = {}
        self.current_metric = None
        self.results_display.clear()
        self.export_latex_button.setEnabled(False)
        self.export_python_button.setEnabled(False)

        if not is_defining_new and not is_custom_selected:
            self.custom_metric_name_input.clear()
            self.custom_metric_coords_input.clear()
            if not self.custom_metric_coords_input.text():
                self.update_metric_grid_state()

        if selection in BUILTIN_METRICS:
            try:
                metric_instance = BUILTIN_METRICS[selection]()
                self.current_metric = MetricTensor(metric_instance.tensor(), metric_instance.syms)
                self.display_metric_preview(self.current_metric) # Display preview
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load built-in metric {selection}: {e}")
                self.metric_combo.setCurrentIndex(0)
        elif is_custom_selected:
            try:
                metric_data = self.custom_metrics[selection]
                coords_str = metric_data['coords']
                matrix_repr_str = metric_data['matrix']

                self.custom_metric_name_input.setText(selection)
                self.custom_metric_coords_input.setText(coords_str)
                # update_metric_grid_state must be called AFTER coords are set
                self.update_metric_grid_state()

                coords = symbols(coords_str)
                # Ensure coords is a tuple for len()
                coords_tuple = coords if isinstance(coords, tuple) else (coords,)
                dim = len(coords_tuple)

                matrix_list_str = ast.literal_eval(matrix_repr_str)
                matrix_list_sympy = []
                for row_str in matrix_list_str:
                    row_sympy = [parse_expr(str(comp)) for comp in row_str]
                    matrix_list_sympy.append(row_sympy)

                self.current_metric = MetricTensor(matrix_list_sympy, coords)

                # Populate the grid - including the disabled lower triangle for visual feedback
                display_dim = min(dim, 4)
                for i in range(display_dim):
                    for j in range(display_dim):
                        if i < len(matrix_list_str) and j < len(matrix_list_str[i]):
                             # Block signals while setting text programmatically
                            self.metric_matrix_inputs[i][j].blockSignals(True)
                            self.metric_matrix_inputs[i][j].setText(str(matrix_list_str[i][j]))
                            self.metric_matrix_inputs[i][j].blockSignals(False)
                        else:
                             self.metric_matrix_inputs[i][j].blockSignals(True)
                             self.metric_matrix_inputs[i][j].clear()
                             self.metric_matrix_inputs[i][j].blockSignals(False)

                self.display_metric_preview(self.current_metric) # Display preview
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load custom metric {selection}: {e}")
                self.metric_combo.setCurrentIndex(0)
                self.custom_metric_coords_input.clear()
                self.update_metric_grid_state()
        elif is_defining_new:
            self.custom_metric_name_input.clear()
            self.custom_metric_coords_input.clear()
            self.update_metric_grid_state()

    def save_or_update_custom_metric(self):
        name = self.custom_metric_name_input.text().strip()
        coords_str = self.custom_metric_coords_input.text().strip()

        if not name or not coords_str:
            QMessageBox.warning(self, "Input Error", "Please provide a name and coordinates.")
            return

        is_update = name in self.custom_metrics
        is_new_name_conflict = not is_update and (name in BUILTIN_METRICS or name in self.custom_metrics)

        if is_new_name_conflict:
             QMessageBox.warning(self, "Name Error", f"A metric with the name '{name}' already exists.")
             return

        try:
            raw_coords = symbols(coords_str)
            coords = raw_coords if isinstance(raw_coords, tuple) else (raw_coords,)
            if not all(isinstance(c, Symbol) for c in coords):
                raise ValueError("Coordinates must be valid comma-separated symbols (e.g., t, x, y, z).")
            dim = len(coords)
            if dim <= 0 or dim > 4:
                raise ValueError("Number of coordinates must be between 1 and 4.")

            # Build the matrix reading only upper triangle, enforcing symmetry
            matrix_list_sympy = [[None for _ in range(dim)] for _ in range(dim)]
            for i in range(dim):
                for j in range(i, dim): # Iterate through upper triangle (i <= j)
                    component_str = self.metric_matrix_inputs[i][j].text().strip()
                    if not component_str:
                        # Check if it's an off-diagonal zero that might be intended
                        is_zero = False
                        try:
                            if parse_expr(component_str) == 0:
                                is_zero = True
                        except:
                            pass
                        if not is_zero: # Allow explicit zero, otherwise raise error
                             raise ValueError(f"Metric component g_{i}{j} cannot be empty.")

                    try:
                        parsed_expr = parse_expr(component_str)
                        matrix_list_sympy[i][j] = parsed_expr
                        if i != j: # Copy to lower triangle
                            matrix_list_sympy[j][i] = parsed_expr
                    except (SyntaxError, TypeError) as parse_error:
                        raise ValueError(f"Invalid expression in g_{i}{j}: '{component_str}'. Error: {parse_error}")

            # Validate the constructed symmetric matrix with MetricTensor
            _ = MetricTensor(matrix_list_sympy, coords)

            # Convert back to list of strings for saving
            matrix_list_str = [[str(comp) for comp in row] for row in matrix_list_sympy]

            self.custom_metrics[name] = {
                "coords": coords_str,
                "matrix": repr(matrix_list_str) # Save the full symmetric matrix representation
            }
            self.save_custom_metrics()

            # --- Update UI ---
            if is_update:
                QMessageBox.information(self, "Success", f"Custom metric '{name}' updated.")
                # Reload the updated metric in the UI
                current_index = self.metric_combo.findText(name)
                if current_index != -1:
                    # Temporarily disconnect to avoid triggering handle_metric_selection recursively
                    self.metric_combo.currentIndexChanged.disconnect(self.handle_metric_selection)
                    self.metric_combo.setCurrentIndex(current_index) # Keep selection
                    # Manually call handle_metric_selection to reload data into fields
                    self.handle_metric_selection(current_index)
                    # Reconnect the signal
                    self.metric_combo.currentIndexChanged.connect(self.handle_metric_selection)
                    # No need to call display_metric_preview here, handle_metric_selection does it
            else: # New metric saved
                QMessageBox.information(self, "Success", f"Custom metric '{name}' saved.")
                # Update combo box and select the new metric
                self.update_metric_combo_box() # This disconnects/reconnects signals
                # Find the index of the newly added metric
                new_index = self.metric_combo.findText(name)
                if new_index != -1:
                    self.metric_combo.setCurrentIndex(new_index) # Select the new metric
                # handle_metric_selection is triggered by setCurrentIndex

        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Failed to validate or save/update custom metric: {e}")
            print(e) # Print detailed error to console for debugging

    def delete_custom_metric(self):
        """Deletes the currently selected custom metric."""
        name = self.custom_metric_name_input.text().strip()

        if not name or name not in self.custom_metrics:
            QMessageBox.warning(self, "Delete Error", "No valid custom metric selected for deletion.")
            return

        reply = QMessageBox.question(self, 'Confirm Delete',
                                     f"Are you sure you want to delete the custom metric '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                del self.custom_metrics[name]
                self.save_custom_metrics()

                index_to_remove = self.metric_combo.findText(name)
                if index_to_remove != -1:
                    self.metric_combo.removeItem(index_to_remove)

                self.metric_combo.setCurrentIndex(0)
                self.results_display.clear()

                QMessageBox.information(self, "Success", f"Custom metric '{name}' deleted.")

            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete custom metric: {e}")
                print(e)

    def display_metric_preview(self, metric_tensor):
        """Displays the metric tensor preview in the results display."""
        if not metric_tensor:
            self.results_display.setHtml("<p>No metric selected.</p>")
            return

        use_string = False
        name = self.metric_combo.currentText()
        coords_expr = metric_tensor.syms
        metric_expr = metric_tensor.tensor()

        coords_png_uri = self._generate_png_data_uri(coords_expr)
        metric_png_uri = self._generate_png_data_uri(metric_expr)

        if coords_png_uri is None or metric_png_uri is None:
            use_string = True

        html_body = f"<h1>Geometry: {name}</h1>"
        html_body += f"<h3> Coordinates:</h3>"
        if coords_png_uri:
            html_body += f'<div style="text-align: center;"><img src="{coords_png_uri}" alt="Coordinates"></div><br>'
        else:
            fallback_msg = "String Fallback"
            if self.rendering_mode == RENDER_TINYTEX: # Add reason only if LaTeX was attempted
                 fallback_msg += f" (Mode: {self.rendering_mode}, PNG failed or skipped)"
            elif self.rendering_mode == RENDER_STRING:
                 fallback_msg += f" (Mode: {self.rendering_mode})"
            html_body += f"<p><i>{fallback_msg}:</i><pre>{str(coords_expr)}</pre></p>"

        html_body += f"<h3>Metric Tensor (g<sub>&mu;&nu;</sub>):</h3>"
        if metric_png_uri:
            html_body += f'<div style="text-align: center;"><img src="{metric_png_uri}" alt="Metric Tensor g_ab"></div><br>'
        else:
            fallback_msg = "String Fallback"
            if self.rendering_mode == RENDER_TINYTEX: # Add reason only if LaTeX was attempted
                 fallback_msg += f" (Mode: {self.rendering_mode}, PNG failed or skipped)"
            elif self.rendering_mode == RENDER_STRING:
                 fallback_msg += f" (Mode: {self.rendering_mode})"
            html_body += f"<p><i>{fallback_msg}:</i><pre>{str(metric_expr)}</pre></p>"

        final_html = html_body
        self.results_display.setHtml(final_html)

    def generate_results_html(self, results):
        """Generates HTML content with embedded PNGs or String for the computed results."""
        if not results:
            return ""

        html_body_parts = []
        html_body_parts.append(f"<h1>Geometry: {self.metric_combo.currentText()}</h1>")

        print(f"HTML Generation: Using {self.rendering_mode} rendering.") # Updated message

        def add_section(title, key, symbol, results_dict, html_list):
            if key in results_dict:
                expr = results_dict[key]
                html_list.append(f"<h3>{title} {symbol}:</h3>")
                png_uri = self._generate_png_data_uri(expr)

                if png_uri:
                    html_list.append(f'<div style="text-align: center;"><img src="{png_uri}" alt="{title}"></div><br>')
                else:
                    fallback_msg = "String Fallback"
                    if self.rendering_mode == RENDER_TINYTEX: # Add reason only if LaTeX was attempted
                         fallback_msg += f" (Mode: {self.rendering_mode}, PNG failed or skipped)"
                    elif self.rendering_mode == RENDER_STRING:
                         fallback_msg += f" (Mode: {self.rendering_mode})"
                    html_list.append(f"<p><i>{fallback_msg}:</i><pre>{str(expr)}</pre></p>")

        coords_expr = results.get('coords', 'N/A')
        html_body_parts.append(f"<h3>Coordinates:</h3>")
        if coords_expr != 'N/A':
            coords_png_uri = self._generate_png_data_uri(coords_expr)
            if coords_png_uri:
                html_body_parts.append(f'<div style="text-align: center;"><img src="{coords_png_uri}" alt="Coordinates"></div><br>')
            else:
                fallback_msg = "String Fallback"
                if self.rendering_mode == RENDER_TINYTEX: # Add reason only if LaTeX was attempted
                     fallback_msg += f" (Mode: {self.rendering_mode}, PNG failed or skipped)"
                elif self.rendering_mode == RENDER_STRING:
                     fallback_msg += f" (Mode: {self.rendering_mode})"
                html_body_parts.append(f"<p><i>{fallback_msg}:</i><pre>{str(coords_expr)}</pre></p>")
        else:
             html_body_parts.append("<p>N/A</p>")

        add_section("Metric Tensor", 'metric', "g<sub>&mu;&nu;</sub>", results, html_body_parts)
        add_section("Christoffel Symbols", 'christoffel', "Γ<sup>&lambda;</sup><sub>&mu;&nu;</sub>", results, html_body_parts)
        add_section("Riemann Curvature Tensor", 'riemann', "R<sup>&lambda;</sup><sub>&mu;&nu;&rho;</sub>", results, html_body_parts)
        add_section("Ricci Tensor", 'ricci_tensor', "R<sub>&mu;&nu;</sub>", results, html_body_parts)
        add_section("Ricci Scalar", 'ricci_scalar', "R", results, html_body_parts)
        add_section("Einstein Tensor", 'einstein', "G<sub>&mu;&nu;</sub>", results, html_body_parts)
        add_section("Weyl Tensor", 'weyl', "C<sup>&lambda;</sup><sub>&mu;&nu;&rho;</sub>", results, html_body_parts)

        html_body = "\n".join(html_body_parts)
        final_html = html_body
        return final_html

    def generate_latex_string(self, results):
        """Generates a LaTeX document string containing the computed results."""
        if not results:
            return ""

        latex_parts = [
            "\\documentclass{article}",
            "\\usepackage{amsmath}",
            "\\usepackage{amssymb}",
            "\\usepackage{amsfonts}",
            "\\usepackage{lmodern}",
            "\\usepackage[margin=1in]{geometry}", # Add margins for better layout
            "\\pagestyle{plain}", # Use plain page style
            "\\begin{document}",
            f"\\section*{{Geometry: {self.metric_combo.currentText()}}}",
        ]

        def add_latex_section(title, key, symbol, results_dict, latex_list):
            if key in results_dict:
                expr = results_dict[key]
                latex_list.append(f"\\subsection*{{{title} ({symbol})}}")
                latex_list.append("\\[")
                latex_list.append(latex(expr))
                latex_list.append("\\]")
                latex_list.append("\\vspace{1em}") # Add some vertical space

        # Add sections in a logical order
        if 'coords' in results:
            latex_parts.append("\\subsection*{Coordinates}")
            latex_parts.append("\\[")
            latex_parts.append(latex(results['coords']))
            latex_parts.append("\\]")
            latex_parts.append("\\vspace{1em}")

        add_latex_section("Metric Tensor", 'metric', "$g_{\\mu\\nu}$", results, latex_parts)
        add_latex_section("Christoffel Symbols", 'christoffel', "$\\Gamma^{\\lambda}{}_{\\mu\\nu}$", results, latex_parts)
        add_latex_section("Riemann Curvature Tensor", 'riemann', "$R^{\\lambda}{}_{\\mu\\nu\\rho}$", results, latex_parts)
        add_latex_section("Ricci Tensor", 'ricci_tensor', "$R_{\\mu\\nu}$", results, latex_parts)
        add_latex_section("Ricci Scalar", 'ricci_scalar', "$R$", results, latex_parts)
        add_latex_section("Einstein Tensor", 'einstein', "$G_{\\mu\\nu}$", results, latex_parts)
        add_latex_section("Weyl Tensor", 'weyl', "$C^{\\lambda}{}_{\\mu\\nu\\rho}$", results, latex_parts)

        latex_parts.append("\\end{document}")
        return "\n".join(latex_parts)

    def generate_python_string(self, results):
        """Generates a Python script string defining the computed results as SymPy objects."""
        if not results:
            return ""

        python_parts = [
            "# Auto-generated Python script from GeoCal",
            "from sympy import *",
            "from sympy.tensor.array import ImmutableDenseNDimArray", # Add import
            "# Add parameters as symbols if needed",
            "",
        ]

        # Define coordinates
        if 'coords' in results:
            coords_repr = ", ".join(map(repr, results['coords']))
            python_parts.append(f"# Coordinates")
            python_parts.append(f"{', '.join(map(str, results['coords']))} = symbols('{coords_repr}')")
            python_parts.append(f"coords = ({', '.join(map(str, results['coords']))})") # Define coords tuple
            python_parts.append("")
        else:
             python_parts.append("# Coordinates not found in results")
             python_parts.append("")


        # Define other tensors/scalars
        tensor_map = {
            'metric': 'metric_tensor',
            'christoffel': 'christoffel_symbols',
            'riemann': 'riemann_tensor',
            'ricci_tensor': 'ricci_tensor',
            'ricci_scalar': 'ricci_scalar', # Scalar
            'einstein': 'einstein_tensor',
            'weyl': 'weyl_tensor',
        }

        for key, var_name in tensor_map.items():
            if key in results:
                expr = results[key]
                python_parts.append(f"# {key.replace('_', ' ').title()}")

                # Check if it's a tensor-like object (Matrix or NDimArray)
                if hasattr(expr, 'tolist') and (isinstance(expr, DenseMatrix) or isinstance(expr, ImmutableDenseNDimArray)):
                    # Use ImmutableDenseNDimArray constructor with tolist()
                    list_repr = repr(expr.tolist())
                    python_parts.append(f"{var_name} = ImmutableDenseNDimArray({list_repr})")
                else:
                    # For scalars or other types, use direct repr()
                    expr_repr = repr(expr)
                    python_parts.append(f"{var_name} = {expr_repr}")

                python_parts.append("")

        return "\n".join(python_parts)

    def compute_curvature(self):
        if not self.current_metric:
            QMessageBox.warning(self, "No Metric", "Please select a metric first.")
            return
        if not isinstance(self.current_metric, MetricTensor):
            QMessageBox.critical(self, "Internal Error", "Selected metric is not a valid MetricTensor object.")
            return
        if not (self.christoffel_check.isChecked() or
                self.riemann_check.isChecked() or self.ricci_tensor_check.isChecked() or
                self.ricci_scalar_check.isChecked() or self.einstein_tensor_check.isChecked() or
                self.weyl_tensor_check.isChecked()):
            QMessageBox.warning(self, "No Selection", "Please select at least one curvature quantity to compute.")
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.results_display.setHtml("<p>Computing...</p>")
        QApplication.processEvents()

        self.computed_results = {}
        self.export_latex_button.setEnabled(False)
        self.export_python_button.setEnabled(False)
        self.latex_render_failed_once = False # Reset flag before computation

        computation_successful = True
        try:
            self.computed_results = {'metric': self.current_metric.tensor(), 'coords': self.current_metric.syms}

            if self.christoffel_check.isChecked():
                chris = ChristoffelSymbols.from_metric(self.current_metric)
                self.computed_results['christoffel'] = chris.tensor()
            else:
                self.computed_results.pop('christoffel', None)

            if self.riemann_check.isChecked():
                riemann = RiemannCurvatureTensor.from_metric(self.current_metric)
                self.computed_results['riemann'] = riemann.tensor()
            else:
                self.computed_results.pop('riemann', None)

            if self.ricci_tensor_check.isChecked():
                ricci = RicciTensor.from_metric(self.current_metric)
                self.computed_results['ricci_tensor'] = ricci.tensor()
            else:
                self.computed_results.pop('ricci_tensor', None)

            if self.ricci_scalar_check.isChecked():
                scalar = RicciScalar.from_metric(self.current_metric)
                self.computed_results['ricci_scalar'] = scalar.expr
            else:
                self.computed_results.pop('ricci_scalar', None)

            if self.einstein_tensor_check.isChecked():
                einstein = EinsteinTensor.from_metric(self.current_metric)
                self.computed_results['einstein'] = einstein.tensor()
            else:
                self.computed_results.pop('einstein', None)

            if self.weyl_tensor_check.isChecked():
                if self.current_metric.dims != 4:
                     QMessageBox.warning(self, "Dimension Error", "Weyl tensor computation is only supported for 4-dimensional metrics.")
                     self.computed_results.pop('weyl', None)
                else:
                    weyl = WeylTensor.from_metric(self.current_metric)
                    self.computed_results['weyl'] = weyl.tensor()
            else:
                self.computed_results.pop('weyl', None)

            html_content = self.generate_results_html(self.computed_results)
            if html_content:
                self.results_display.setHtml(html_content)
            else:
                QMessageBox.warning(self, "No Results", "No curvature quantities were selected or generated.")
                computation_successful = False
                self.results_display.setHtml("<p>No results to display.</p>")

            self.export_latex_button.setEnabled(computation_successful and bool(self.computed_results))
            self.export_python_button.setEnabled(computation_successful and bool(self.computed_results))
        except Exception as e:
            computation_successful = False
            QMessageBox.critical(self, "Computation Error", f"An error occurred during tensor computation: {e}")
            print("Computation Error", f"An error occurred during tensor computation: {e}")
            error_html = f"<p><b>Computation Error:</b><br>{e}</p>"
            self.results_display.setHtml(error_html)
            self.computed_results = {}

        finally:
            QApplication.restoreOverrideCursor()
            if not computation_successful or not self.computed_results:
                self.export_latex_button.setEnabled(False)
                self.export_python_button.setEnabled(False)

    def export_latex(self):
        """Exports the computed results as a .tex file."""
        latex_to_save = self.generate_latex_string(self.computed_results)

        if not latex_to_save:
            QMessageBox.warning(self, "No Results", "No results available to export.")
            return

        options = QFileDialog.Options()
        # Suggest a filename based on the metric name
        metric_name = self.metric_combo.currentText().replace(" ", "_").replace("/", "_")
        suggested_filename = f"{metric_name}_geometry.tex" if metric_name != "Select Metric..." else "geometry_export.tex"

        fileName, _ = QFileDialog.getSaveFileName(self, "Save LaTeX Output", suggested_filename, "LaTeX Files (*.tex);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'w', encoding='utf-8') as f:
                    f.write(latex_to_save)
                QMessageBox.information(self, "Export Successful", f"LaTeX output saved to {fileName}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save LaTeX file: {e}")

    def export_python(self):
        """Exports the computed results as a .py file."""
        python_to_save = self.generate_python_string(self.computed_results)

        if not python_to_save:
            QMessageBox.warning(self, "No Results", "No results available to export.")
            return

        options = QFileDialog.Options()
        # Suggest a filename based on the metric name
        metric_name = self.metric_combo.currentText().replace(" ", "_").replace("/", "_")
        suggested_filename = f"{metric_name}_geometry.py" if metric_name != "Select Metric..." else "geometry_export.py"

        fileName, _ = QFileDialog.getSaveFileName(self, "Save Python Output", suggested_filename, "Python Files (*.py);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'w', encoding='utf-8') as f:
                    f.write(python_to_save)
                QMessageBox.information(self, "Export Successful", f"Python script saved to {fileName}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save Python file: {e}")

    def closeEvent(self, event):
        self.settings.setValue("customMetricsDirectory", self.custom_metrics_dir)
        self.settings.remove("latexExecutablePath")
        self.settings.setValue("renderingMode", self.rendering_mode)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CurvatureApp()
    window.show()
    sys.exit(app.exec())

