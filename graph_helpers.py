import numpy as np
import itertools
from graph_tool import Graph, GraphView
from graph_tool.search import bfs_search, BFSVisitor
from graph_tool.topology import random_spanning_tree

from collections import defaultdict


def build_graph_from_edges(edges):
    """returns Graph (a new one)
    """
    g = Graph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


def filter_graph_by_edges(g, edges):
    """returns GraphView
    """
    efilt = g.new_edge_property('bool')
    efilt.set_value(False)
    for i, j in edges:
        efilt[g.edge(i, j)] = True
    return GraphView(g, efilt=efilt)


def get_leaves(t):
    assert t.is_directed() is False
    return np.nonzero(t.degree_property_map(deg='out').a == 1)[0]


def extract_nodes(g):
    return [int(u) for u in g.vertices()]


def extract_edges(g):
    return [(int(u), int(v)) for u, v in g.edges()]


def extract_steiner_tree(sp_tree, terminals):
    """given spanning tree and terminal nodes, extract the steiner tree that spans terminals
    
    Param:
    ------------

    sp_tree: spanning tree
    terminals: list of integers

    Return:
    -----------
    GraphView: the steiner tree
    
    algorithm idea:

    1. BFS from `s \in terminals`, to the other terminals, `terminals - {s}`
    2. BFS back from `v \in terminals-{s}` to s and collect the edges
       - note that BFS is terminated if some node is already traversed
         (in other words, edges are added already)

    running time: O(E)
    """
    if not isinstance(terminals, list):
        terminals = list(set(terminals))

    pred = dict(zip(range(sp_tree.num_vertices()), itertools.repeat(None)))

    class Visitor(BFSVisitor):
        """record the predecessor"""

        def __init__(self, pred):
            self.pred = pred
        
        def tree_edge(self, e):
            self.pred[int(e.target())] = int(e.source())
    
    vis = Visitor(pred)
    
    efilt = sp_tree.new_edge_property('bool')
    efilt.set_value(False)

    vfilt = sp_tree.new_vertex_property('bool')
    vfilt.set_value(False)
    
    s = terminals.pop()
    bfs_search(sp_tree, source=s, visitor=vis)

    vfilt[s] = True
    while len(terminals) > 0:
        x = terminals.pop()
        vfilt[x] = True

        y = vis.pred[x]
        while y:
            efilt[sp_tree.edge(x, y)] = True
            vfilt[y] = True
            if not vfilt[y]:
                break
            x = y
            y = vis.pred[x]

    return GraphView(sp_tree, vfilt=vfilt, efilt=efilt)


def gen_random_spanning_tree(g):
    efilt = random_spanning_tree(g)
    return GraphView(g, efilt=efilt)


def contract_graph_by_nodes(g, nodes, weights=None):
    """
    contract graph by nodes (only for undirected)

    note: the supernode is node 0 in the new graph

    Params:
    ----------
    g: Graph, undirected
    weights: edge_property_map
    nodes: list of ints

    Returns:
    ----------
    - Graph: a contracted graph where `nodes` are merged into a supernode
    - edge_property_map: new weight
    """
    if len(nodes) == 1:
        return g, weights

    nodes = set(nodes)

    # print('nodes:', nodes)
    
    # re-align the nodes
    # `v \in nodes` are considered node 0
    # get the old node to new node mapping
    o2n_map = {}
    c = 1
    for v in g.vertices():
        v = int(v)
        if v not in nodes:
            o2n_map[v] = c
            c += 1
        else:
            o2n_map[v] = 0
    # print('o2n_map:', o2n_map)

    # calculate new edges and new weights
    e2w = defaultdict(float)
    for e in g.edges():
        u, v = map(int, [e.source(), e.target()])
        nu, nv = sorted([o2n_map[u], o2n_map[v]])
        if weights:
            e2w[(nu, nv)] += weights[g.edge(u, v)]
        else:
            e2w[(nu, nv)] += 1

    # print('e2w:', e2w)

    # create the new graph
    new_g = Graph(directed=False)
    for _ in range(g.num_vertices() - len(nodes) + 1):
        new_g.add_vertex()

    for u, v in e2w:
        new_g.add_edge(u, v)

    new_weights = new_g.new_edge_property('float')
    for (u, v), w in e2w.items():
        new_weights[new_g.edge(u, v)] = w

    return new_g, new_weights

