from sympy import *

# Geometry: dS(closed)

coords = symbols('t, psi, theta, phi')
t = symbols('t')
psi = symbols('psi')
theta = symbols('theta')
phi = symbols('phi')
alpha = symbols('alpha')

metric_tensor = [[-1, 0, 0, 0], [0, alpha**2*cosh(t/alpha)**2, 0, 0], [0, 0, alpha**2*sin(psi)**2*cosh(t/alpha)**2, 0], [0, 0, 0, alpha**2*sin(psi)**2*sin(theta)**2*cosh(t/alpha)**2]]

christoffel_symbols = [[[0, 0, 0, 0], [0, alpha*sinh(t/alpha)*cosh(t/alpha), 0, 0], [0, 0, alpha*sin(psi)**2*sinh(t/alpha)*cosh(t/alpha), 0], [0, 0, 0, alpha*sin(psi)**2*sin(theta)**2*sinh(t/alpha)*cosh(t/alpha)]], [[0, sinh(t/alpha)/(alpha*cosh(t/alpha)), 0, 0], [sinh(t/alpha)/(alpha*cosh(t/alpha)), 0, 0, 0], [0, 0, -sin(psi)*cos(psi), 0], [0, 0, 0, -sin(psi)*sin(theta)**2*cos(psi)]], [[0, 0, sinh(t/alpha)/(alpha*cosh(t/alpha)), 0], [0, 0, cos(psi)/sin(psi), 0], [sinh(t/alpha)/(alpha*cosh(t/alpha)), cos(psi)/sin(psi), 0, 0], [0, 0, 0, -sin(theta)*cos(theta)]], [[0, 0, 0, sinh(t/alpha)/(alpha*cosh(t/alpha))], [0, 0, 0, cos(psi)/sin(psi)], [0, 0, 0, cos(theta)/sin(theta)], [sinh(t/alpha)/(alpha*cosh(t/alpha)), cos(psi)/sin(psi), cos(theta)/sin(theta), 0]]]

riemann_tensor = None # Not computed

ricci_tensor = [[-3/alpha**2, 0, 0, 0], [0, 3*cosh(t/alpha)**2, 0, 0], [0, 0, 3*sin(psi)**2*cosh(t/alpha)**2, 0], [0, 0, 0, 3*sin(psi)**2*sin(theta)**2*cosh(t/alpha)**2]]

ricci_scalar = 12/alpha**2

einstein_tensor = None # Not computed

weyl_tensor = None # Not computed
