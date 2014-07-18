#!/usr/bin/env python

import numpy as np
from scipy import sparse
from sympy import symbols, Function, Matrix, simplify

import pendulum


def test_output_equations():

    # four states (cols), and 5 time steps (rows)
    x = np.array([[1, 2, 3, 4],
                  [5, 6, 7, 8],
                  [9, 10, 11, 12],
                  [13, 14, 15, 16],
                  [17, 18, 19, 20]])

    y = pendulum.output_equations(x)

    expected_y = np.array([[1, 2],
                           [5, 6],
                           [9, 10],
                           [13, 14],
                           [17, 18]])

    np.testing.assert_allclose(y, expected_y)


def test_objective_function():

    M = 5
    o = 2
    n = 2 * o
    q = 3
    h = 0.01

    time = np.linspace(0.0, (M - 1) * h, num=M)
    y_measured = np.random.random((M, o))  # measured coordinates
    x_model = np.hstack((y_measured, np.random.random((M, o))))
    free = np.hstack((x_model.flatten(), np.random.random(q)))

    cost = pendulum.objective_function(free, M, n, h, time, y_measured)

    np.testing.assert_allclose(cost, 0.0, atol=1e-15)


def test_substitute_matrix():

    A = np.arange(1, 13, dtype=float).reshape(3, 4)
    sub = np.array([[21, 22], [23, 24]])
    new_A = pendulum.substitute_matrix(A, [1, 2], [0, 2], sub)
    expected = np.array([[1, 2, 3, 4],
                         [21, 6, 22, 8],
                         [23, 10, 24, 12]], dtype=float)

    np.testing.assert_allclose(new_A, expected)

    A = sparse.lil_matrix(np.zeros((3, 4)))
    sub = np.array([[21, 22], [23, 24]])
    new_A = pendulum.substitute_matrix(A, [1, 2], [0, 2], sub)
    expected = np.array([[0, 0, 0, 0],
                         [21, 0, 22, 0],
                         [23, 0, 24, 0]], dtype=float)

    np.testing.assert_allclose(new_A.todense(), expected)


def test_discrete_symbols():
    t = symbols('t')
    v, x = symbols('v, x', cls=Function)
    f = symbols('f', cls=Function)

    v = v(t)
    x = x(t)
    f = f(t)

    states = [v, x]
    specified = [f]

    current_states, previous_states, current_specified, interval = \
        pendulum.discrete_symbols(states, specified)

    xi, vi, xp, vp, fi, h = symbols('xi, vi, xp, vp, fi, h')

    assert current_states[0] is vi
    assert current_states[1] is xi
    assert previous_states[0] is vp
    assert previous_states[1] is xp
    assert current_specified[0] is fi
    assert interval is h


def test_f_minus_ma():

    t = symbols('t')
    x, v = symbols('x, v', cls=Function)
    m, c, k = symbols('m, c, k')
    f = symbols('f', cls=Function)

    x = x(t)
    v = v(t)
    f = f(t)

    states = [x, v]

    mass_matrix = Matrix([[1, 0], [0, m]])
    forcing_vector = Matrix([v, -c * v - k * x + f])

    constraint = pendulum.f_minus_ma(mass_matrix, forcing_vector, states)

    expected = Matrix([x.diff() - v,
                       m * v.diff() + c * v + k * x - f])

    assert simplify(constraint - expected) == Matrix([0, 0])


def test_discretize():

    t, h = symbols('t, h')
    x, v = symbols('x, v', cls=Function)
    m, c, k = symbols('m, c, k')
    f = symbols('f', cls=Function)

    x = x(t)
    v = v(t)
    f = f(t)

    states = [x, v]
    specified = [f]

    eoms = Matrix([x.diff() - v,
                   m * v.diff() + c * v + k * x - f])

    discrete_eoms = pendulum.discretize(eoms, states, specified, h)

    xi, vi, xp, vp, fi = symbols('xi, vi, xp, vp, fi')

    expected = Matrix([(xi - xp) / h - vi,
                       m * (vi - vp) / h + c * vi + k * xi - fi])

    assert simplify(discrete_eoms - expected) == Matrix([0, 0])


def test_general_constraint():

    t, h = symbols('t, h')
    x, v = symbols('x, v', cls=Function)
    m, c, k = symbols('m, c, k')
    f = symbols('f', cls=Function)

    x = x(t)
    v = v(t)
    f = f(t)

    states = [x, v]
    specified = [f]

    xi, vi, xp, vp, fi = symbols('xi, vi, xp, vp, fi')

    eom_vector = Matrix([(xi - xp) / h - vi,
                         m * (vi - vp) / h + c * vi + k * xi - fi])

    constrain = pendulum.general_constraint(eom_vector, states, specified,
                                            [m, c, k])

    state_values = np.array([[1, 2, 3, 4],
                             [5, 6, 7, 8]])
    specified_values = np.array([2, 2, 2, 2])
    constant_values = np.array([1.0, 2.0, 3.0])
    m, c, k = constant_values
    h = 0.01

    result = constrain(state_values, specified_values, constant_values, h)

    expected_dynamic = np.zeros(3)
    expected_kinematic = np.zeros(3)

    for i in [1, 2, 3]:

        xi, vi = state_values[:, i]
        xp, vp = state_values[:, i - 1]
        fi = specified_values[i]

        expected_dynamic[i - 1] = m * (vi - vp) / h + c * vi + k * xi - fi
        expected_kinematic[i - 1] = (xi - xp) / h - vi

    expected = np.hstack((expected_kinematic, expected_dynamic))

    np.testing.assert_allclose(result, expected)


def test_general_constraint_jacobian():

    t, h = symbols('t, h')
    x, v = symbols('x, v', cls=Function)
    m, c, k = symbols('m, c, k')
    f = symbols('f', cls=Function)

    x = x(t)
    v = v(t)
    f = f(t)

    states = [x, v]
    specified = [f]
    constants = [m, c, k]
    free_constants = [k]

    xi, vi, xp, vp, fi = symbols('xi, vi, xp, vp, fi')

    eom_vector = Matrix([(xi - xp) / h - vi,
                         m * (vi - vp) / h + c * vi + k * xi - fi])

    jacobian = pendulum.general_constraint_jacobian(eom_vector, states,
                                                    specified, constants,
                                                    free_constants)

    state_values = np.array([[1, 2, 3, 4],   # x
                             [5, 6, 7, 8]])  # v
    specified_values = np.array([2, 2, 2, 2])
    constant_values = np.array([1.0, 2.0, 3.0])

    x = state_values[0]
    m, c, k = constant_values
    h = 0.01

    result = jacobian(state_values, specified_values, constant_values, h)

    # jacobian of eom_vector wrt vi, xi, xp, vp, k
    #    [     vi,  xi,   vp,   xp,  k]
    # x: [     -1, 1/h,    0, -1/h,  0]
    # v: [c + m/h,   k, -m/h,    0, xi]

    expected_jacobian = np.array(
        #     x1,     x2,     x3,    x4,     v1,        v2,         v3,        v4,    k
        [[-1 / h,  1 / h,      0,     0,      0,        -1,          0,         0,    0],
         [     0, -1 / h,  1 / h,     0,      0,         0,         -1,         0,    0],
         [     0,      0, -1 / h, 1 / h,      0,         0,          0,        -1,    0],
         [     0,      k,      0,     0, -m / h, c + m / h,          0,         0, x[1]],
         [     0,      0,      k,     0,      0,    -m / h,  c + m / h,         0, x[2]],
         [     0,      0,      0,     k,      0,         0,      -m /h, c + m / h, x[3]]])

    np.testing.assert_allclose(result.todense(), expected_jacobian)


def test_wrap_constraint():

    t, h = symbols('t, h')
    x, v = symbols('x, v', cls=Function)
    m, c, k = symbols('m, c, k')
    f = symbols('f', cls=Function)

    x = x(t)
    v = v(t)
    f = f(t)

    states = [x, v]
    specified = [f]
    constants = [m, c, k]
    free_constants = [k]

    xi, vi, xp, vp, fi = symbols('xi, vi, xp, vp, fi')

    eom_vector = Matrix([(xi - xp) / h - vi,
                         m * (vi - vp) / h + c * vi + k * xi - fi])

    gen_con = pendulum.general_constraint(eom_vector, states, specified,
                                          constants)

    gen_jac = pendulum.general_constraint_jacobian(eom_vector, states,
                                                   specified, constants,
                                                   free_constants)

    num_time_steps = 4
    num_states = 2
    interval_value = 0.01
    fixed_constants = {m: 1.0, c: 2.0}
    fixed_specified = {fi: np.array([2, 2, 2, 2])}

    specified_syms = [fi]

    constrain = pendulum.wrap_constraint(gen_con, num_time_steps,
                                         num_states, interval_value,
                                         constants, specified_syms,
                                         fixed_constants, fixed_specified)

    free = np.array([1, 2, 3, 4, 5, 6, 7, 8, 3.0])

    result = constrain(free)

    expected_dynamic = np.zeros(3)
    expected_kinematic = np.zeros(3)

    state_values = np.array([[1, 2, 3, 4],
                             [5, 6, 7, 8]])
    specified_values = np.array([2, 2, 2, 2])
    constant_values = np.array([1.0, 2.0, 3.0])
    m, c, k = constant_values
    h = interval_value

    for i in [1, 2, 3]:

        xi, vi = state_values[:, i]
        xp, vp = state_values[:, i - 1]
        fi = specified_values[i]

        expected_kinematic[i - 1] = (xi - xp) / h - vi
        expected_dynamic[i - 1] = m * (vi - vp) / h + c * vi + k * xi - fi

    expected = np.hstack((expected_kinematic, expected_dynamic))

    np.testing.assert_allclose(result, expected)

    jacobian = pendulum.wrap_constraint(gen_jac, num_time_steps, num_states,
                                        interval_value, constants,
                                        specified_syms, fixed_constants,
                                        fixed_specified)

    result = jacobian(free)

    x = state_values[0]

    expected_jacobian = np.array(
        #     x1,     x2,     x3,    x4,     v1,        v2,         v3,        v4,    k
        [[-1 / h,  1 / h,      0,     0,      0,        -1,          0,         0,    0],
         [     0, -1 / h,  1 / h,     0,      0,         0,         -1,         0,    0],
         [     0,      0, -1 / h, 1 / h,      0,         0,          0,        -1,    0],
         [     0,      k,      0,     0, -m / h, c + m / h,          0,         0, x[1]],
         [     0,      0,      k,     0,      0,    -m / h,  c + m / h,         0, x[2]],
         [     0,      0,      0,     k,      0,         0,      -m /h, c + m / h, x[3]]])

    np.testing.assert_allclose(result.todense(), expected_jacobian)