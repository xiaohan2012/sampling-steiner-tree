import numpy as np


@profile
def num_matching_trees(T, node, value):
    """
    Args:
    ---------
    T: list of set of ints, list of trees represented by nodes
    node: node to filter
    value: value to filter

    Returns:
    ---------
    int: number of matching trees
    """
    if value == 1:  # infected
        return len([t for t in T if node in t])
    else:  # uninfected
        return len([t for t in T if node not in t])


def matching_trees(T, node, value):
    """
    T: list of set of ints, list of trees represented by nodes
    node: node to filter
    value: value to filter
    """
    if value == 1:  # infected
        return [t for t in T if node in t]
    else:  # uninfected
        return [t for t in T if node not in t]
        
# @profile
def prediction_error(q, y_hat, T, hidden_nodes):
    # filter T by (q, y_hat)
    sub_T = matching_trees(T, q, y_hat)
    N = len(sub_T)
    error = 0
    for u in hidden_nodes:
        try:
            p = len(matching_trees(sub_T, u, 0)) / N
            if p == 0 or p == 1:
                raise ZeroDivisionError
            error -= (p * np.log(p) + (1-p) * np.log(1-p))
        except ZeroDivisionError:
            # entropy is zero
            pass

    return error

# @profile
def query_score(q, T, hidden_nodes):
    assert q not in hidden_nodes
    score = 0
    if True:
        for y_hat in [0, 1]:
            p = len(matching_trees(T, q, y_hat)) / len(T)
            score += p * prediction_error(q, y_hat, T, hidden_nodes)
            # if q in {0, 89, 99, 9}:  # debug
            # print('p(q={}, y={})={}'.format(q, y_hat, p))
    else:
        score += prediction_error(q, 1, T, hidden_nodes)
    return score
