# GeoCal: Curvature Calculator

GeoCal is a desktop application for computing various curvature quantities in differential geometry and general relativity. It allows users to select predefined metrics, define custom metrics, and calculate tensors like the Christoffel symbols, Riemann tensor, Ricci tensor/scalar, Einstein tensor, and Weyl tensor. Results can be displayed using LaTeX rendering (via TinyTeX or a system installation) or as plain text, and can be exported to `.tex` or `.py` files.

## Features

*   **Metric Selection:** Choose from built-in metrics (e.g., Schwarzschild, Kerr, FLRW) or define your own custom metrics.
*   **Custom Metrics:** Define metrics with custom coordinates and components using SymPy expressions. Save and manage your custom metrics.
*   **Curvature Computations:** Calculate:
    *   Christoffel Symbols (Γ<sup>λ</sup><sub>μν</sub>)
    *   Riemann Curvature Tensor (R<sup>λ</sup><sub>μνρ</sub>)
    *   Ricci Tensor (R<sub>μν</sub>)
    *   Ricci Scalar (R)
    *   Einstein Tensor (G<sub>μν</sub>)
    *   Weyl Tensor (C<sup>λ</sup><sub>μνρ</sub>) (for 4D metrics)
*   **Rendering Options:**
    *   **LaTeX:** Renders mathematical expressions as high-quality images using LaTeX (requires TinyTeX or a system LaTeX installation).
    *   **Plain Text:** Displays results as plain text SymPy string representations.
*   **Export:** Export computed results to:
    *   `.tex` file: A standalone LaTeX document.
    *   `.py` file: A Python script defining the results as SymPy objects.
*   **Cross-Platform:** Built with Python and PySide6.

## Screenshot

![Display](/Screenshot%20-%20GeoCal.png)

## Installation

You can install GeoCal using pre-built packages or by running from source.

### macOS (.dmg)

1.  Download the latest `GeoCal-macOS.dmg` file from the [Releases](https://github.com/seangryb/differential_geometry/releases) page.
2.  Double-click the `.dmg` file to open it.
3.  Drag the `GeoCal` application icon into your `Applications` folder.
4.  You may need to right-click (or Ctrl-click) the application and select "Open" the first time due to macOS Gatekeeper security.
5.  The application includes a bundled version of TinyTeX for LaTeX rendering.

### Windows (.zip)

1.  Download the latest `GeoCal-Windows.zip` file from the [Releases](https://github.com/your-repo/GeoCal/releases) page.
2.  Extract the contents of the `.zip` file to a location of your choice (e.g., `C:\Program Files\GeoCal`).
3.  Navigate into the extracted folder and run `GeoCal.exe` (or the main executable).
4.  The application includes a bundled version of TinyTeX for LaTeX rendering.

### From Source

Running from source requires Python, pip, and potentially a LaTeX distribution.

**Prerequisites:**

*   Python 3.8 or later.
*   pip (Python package installer).
*   Git (optional, for cloning).
*   **LaTeX Requirement (for LaTeX rendering mode):** You need *one* of the following:
    *   **Option 1: System LaTeX Installation:** Install a LaTeX distribution like [TeX Live](https://www.tug.org/texlive/) (recommended for Linux/macOS) or [MiKTeX](https://miktex.org/) (recommended for Windows). Ensure that the `latex` and `dvipng` executables are included in your system's PATH environment variable.
    *   **Option 2: Bundled TinyTeX:** Download a minimal [TinyTeX v1](https://yihui.org/tinytex/) distribution. Ensure it includes the `dvipng` package. Place the *entire* `TinyTeX` directory inside the root directory of the GeoCal source code (the same directory as `curvature_app.py`). The application will automatically detect and use `./TinyTeX/bin/...` if it exists.

**Steps:**

1.  **Get the Source Code:**
    *   Clone the repository: `git clone https://github.com/seangryb/differential_geometry.git`
    *   Or download the source code `.zip` and extract it.
2.  **Navigate to Directory:**
    ```bash
    cd GeoCal
    ```
3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Ensure LaTeX is Set Up:** Verify either your system LaTeX (Option 1) or the bundled TinyTeX (Option 2) is correctly configured as described in the prerequisites.
6.  **Run the Application:**
    ```bash
    python curvature_app.py
    ```

## Usage

1.  **Launch GeoCal.**
2.  **Select a Metric:**
    *   Use the dropdown menu to choose a built-in metric.
    *   Select "Add New..." to define a custom metric:
        *   Enter a unique name.
        *   Define coordinates as comma-separated symbols (e.g., `t, r, theta, phi`).
        *   Fill in the upper triangle of the metric tensor components (g<sub>μν</sub>) using SymPy-compatible expressions. The lower triangle will auto-fill due to symmetry.
        *   Click "Save / Update". Your metric will appear under "--- Custom ---".
    *   Select a previously saved custom metric to view, edit (only components/coords, not name), or delete it.
3.  **Choose Rendering Mode (Optional):** Go to `Options -> Rendering Mode` and select `LaTeX` (requires valid LaTeX setup) or `Plain Text`.
4.  **Select Curvature Quantities:** Check the boxes for the tensors/scalars you want to compute.
5.  **Compute:** Click the "Compute Curvature" button.
6.  **View Results:** The results will be displayed in the right-hand panel, rendered according to the selected mode.
7.  **Export (Optional):** If computations were successful, click "Export .tex" or "Export .py" to save the results.
8.  **Custom Metrics Directory:** Use the "Browse..." button to change the directory where custom metric definitions (`custom_metrics.json`) are stored.

## Dependencies

*   [Python](https://www.python.org/)
*   [PySide6](https://doc.qt.io/qtforpython/) (for the GUI)
*   [SymPy](https://www.sympy.org/) (for symbolic mathematics)
*   [EinsteinPy](https://einsteinpy.org/) (for tensor computations)
*   [LaTeX](https://www.latex-project.org/) (optional, for rendering) - Either TinyTeX or a full system installation (TeX Live, MiKTeX).

