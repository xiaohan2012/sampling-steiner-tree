# coding: utf-8


import os
import pickle as pkl
import argparse
from tqdm import tqdm
from joblib import Parallel, delayed

from helpers import load_cascades
from inference import infection_probability
from graph_helpers import (load_graph_by_name, remove_filters,
                           observe_uninfected_node)
from sample_pool import TreeSamplePool
from random_steiner_tree.util import from_gt, isolate_vertex
from tree_stat import TreeBasedStatistics


def infer_probas_for_multiple_queries(g, obs, c, queries,
                                      sampling_method, root_sampler, n_samples):
    g = remove_filters(g)
    gi = from_gt(g)
    obs_inf = set(obs)
    probas_list = []

    sampler = TreeSamplePool(g, n_samples=n_samples,
                             method=sampling_method,
                             gi=gi,
                             return_tree_nodes=True)
    estimator = TreeBasedStatistics(g)
    sampler.fill(obs,
                 root_sampler=root_sampler)
    estimator.build_matrix(sampler.samples)
    for q in queries:
        if c[q] >= 0:  # infected
            obs_inf |= {q}
        else:
            observe_uninfected_node(g, q, obs_inf)
            isolate_vertex(gi, q)

        # update samples
        label = int(c[q] >= 0)
        new_samples = sampler.update_samples(obs_inf, q, label)
        estimator.update_trees(new_samples, q, label)

        # new probas
        probas = infection_probability(g, obs_inf, sampler, error_estimator=estimator)
        probas_list.append(probas)

    return probas_list, sampler, estimator


def one_round(g, obs, c, c_path, method,
              query_dirname, inf_proba_dirname,
              n_samples=250,
              sampling_method='loop_erased',
              debug=False):
    cid = os.path.basename(c_path).split('.')[0]
    probas_dir = os.path.join(inf_proba_dirname, method)
    if not os.path.exists(probas_dir):
        os.makedirs(probas_dir)
    path = os.path.join(probas_dir, '{}.pkl'.format(cid))
    
    if os.path.exists(path):
        # if computed, ignore
        return

    query_log_path = os.path.join(query_dirname, method, '{}.pkl'.format(cid))
    queries, _ = pkl.load(open(query_log_path, 'rb'))

    # the real part
    probas_list, _, _ = infer_probas_for_multiple_queries(g, obs, c, queries,
                                                          sampling_method, n_samples)

    pkl.dump(probas_list, open(path, 'wb'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-g', '--graph',
                        help='graph name')
    parser.add_argument('-s', '--n_samples', type=int,
                        default=100,
                        help='number of samples')

    parser.add_argument('-c', '--cascade_dir',
                        help='directory to read cascades')
    parser.add_argument('-q', '--query_dirname',
                        help='directory of queries')
    parser.add_argument('-p', '--inf_proba_dirname',
                        help='directory to store the inferred probabilities')

    args = parser.parse_args()

    graph_name = args.graph
    n_samples = args.n_samples

    query_dirname = args.query_dirname
    inf_proba_dirname = args.inf_proba_dirname

    g = load_graph_by_name(graph_name)

    cascades = load_cascades(args.cascade_dir)

    methods = ['pagerank', 'random', 'entropy', 'prediction_error']

    Parallel(n_jobs=1)(delayed(one_round)(g, obs, c, path, method, query_dirname, inf_proba_dirname)
                       for path, (obs, c) in tqdm(cascades)
                       for method in methods)

