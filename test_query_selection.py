import pytest
from query_selection import (RandomQueryGenerator, EntropyQueryGenerator,
                             PRQueryGenerator, PredictionErrorQueryGenerator,
                             NoMoreQuery)
from simulator import Simulator
from graph_helpers import remove_filters, get_edge_weights
from fixture import g
from sample_pool import TreeSamplePool
from random_steiner_tree.util import from_gt
from tree_stat import TreeBasedStatistics

from test_helpers import check_tree_samples, check_error_esitmator


@pytest.mark.parametrize("query_method", ['random', 'pagerank', 'entropy', 'error'])
@pytest.mark.parametrize("sampling_method", ['cut_naive', 'cut', 'loop_erased'])
@pytest.mark.parametrize("with_inc_sampling", [True, False])
@pytest.mark.parametrize("root_sampler", [None, 'pagerank'])
def test_query_method(g, query_method, sampling_method, root_sampler, with_inc_sampling):
    print('query_method: ', query_method)
    print('sampling_method: ', sampling_method)
    print('roo_sampler: ', root_sampler)

    gv = remove_filters(g)
    edge_weights = get_edge_weights(gv)
    
    if query_method in {'entropy', 'error'}:
        gi = from_gt(g, edge_weights)
    else:
        gi = None

    pool = TreeSamplePool(gv,
                          n_samples=20,
                          method=sampling_method,
                          edge_weights=edge_weights,
                          gi=gi,
                          return_tree_nodes=True,  # using tree nodes
                          with_inc_sampling=with_inc_sampling
    )

    if query_method == 'random':
        q_gen = RandomQueryGenerator(gv)
    elif query_method == 'pagerank':
        q_gen = PRQueryGenerator(gv)
    elif query_method == 'entropy':
        error_estimator = TreeBasedStatistics(gv)
        q_gen = EntropyQueryGenerator(gv, pool,
                                      error_estimator=error_estimator,
                                      normalize_p='div_max')
    elif query_method == 'error':
        error_estimator = TreeBasedStatistics(gv)
        q_gen = PredictionErrorQueryGenerator(gv, pool,
                                              error_estimator=error_estimator,
                                              prune_nodes=True,
                                              n_node_samples=10,
                                              root_sampler=root_sampler,
                                              normalize_p='div_max')

    sim = Simulator(gv, q_gen, gi=gi, print_log=True)
    print('simulator created')
    n_queries = 10
    qs, aux = sim.run(n_queries)
    print('sim.run finished')
    
    assert len(qs) == n_queries
    assert set(qs).intersection(set(aux['obs'])) == set()

    if query_method in {'entropy', 'error'}:
        check_tree_samples(qs, aux['c'], q_gen.sampler.samples)
    if query_method == 'error':
        # ensure that error estimator updates its tree samples
        check_error_esitmator(qs, aux['c'], error_estimator)


def test_no_more_query(g):
    gv = remove_filters(g)

    q_gen = RandomQueryGenerator(gv)
    sim = Simulator(gv, q_gen, print_log=True)

    qs, aux = sim.run(g.num_vertices()+100)
    assert len(qs) < g.num_vertices()


def build_simulator_using_prediction_error_query_selector(g, **kwargs):
    gv = remove_filters(g)
    gi = from_gt(g)
    pool = TreeSamplePool(gv,
                          n_samples=1000,
                          method='loop_erased',
                          gi=gi,
                          return_tree_nodes=True  # using tree nodes
    )

    q_gen = PredictionErrorQueryGenerator(gv, pool,
                                          error_estimator=TreeBasedStatistics(gv),
                                          root_sampler=None,
                                          **kwargs)
    return Simulator(gv, q_gen, gi=gi, print_log=True), q_gen


@pytest.mark.parametrize("repeat_id", range(5))
def test_prediction_error_with_candidate_pruning(g, repeat_id):
    min_probas = [0, 0.1, 0.2, 0.3, 0.4]
    cand_nums = []

    for min_proba in min_probas:
        sim, q_gen = build_simulator_using_prediction_error_query_selector(
            g, prune_nodes=True, min_proba=min_proba)
        
        sim.run(0)  # just get the candidates
        q_gen.prune_candidates()  # and prune the candidates

        cand_nums.append(len(q_gen._cand_pool))

    # number of candidates should be decreasing (more accurately, non-increasing)
    for prev, cur in zip(cand_nums, cand_nums[1:]):
        assert prev >= cur


def test_prediction_error_sample_nodes_for_estimation(g):
    n_node_samples_list = [10, 20, 30, 40, 50]
    for n_node_samples in n_node_samples_list:
        sim, q_gen = build_simulator_using_prediction_error_query_selector(
            g, n_node_samples=n_node_samples)
        sim.run(0)

        samples = q_gen._sample_nodes_for_estimation()
        assert len(samples) == n_node_samples
    
