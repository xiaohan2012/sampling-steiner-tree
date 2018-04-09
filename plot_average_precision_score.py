# coding: utf-8

import os
import numpy as np
import matplotlib
import argparse
matplotlib.use('pdf')

from matplotlib import pyplot as plt
from cycler import cycler
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

from helpers import load_cascades
from graph_helpers import load_graph_by_name
from eval_helpers import aggregate_scores_over_cascades_by_methods, precision_at_cascade_size

np.seterr(divide='raise', invalid='raise')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-g', '--graph_name', help='graph name')
    parser.add_argument('-d', '--data_id', help='data id (e.g, "grqc-mic-o0.1")')

    # eval method
    parser.add_argument('-e', '--eval_method',
                        choices=('ap', 'auc', 'precision_at_cascade_size'),
                        help='evalulation method')
    parser.add_argument('--eval_with_mask',
                        type=bool,
                        help='whether evaluate with masks or not. If True, queries and obs are excluded')
    
    # root directory names
    parser.add_argument('-c', '--cascade_dirname', help='cascade directory name')
    parser.add_argument('--inf_dirname', help='')
    parser.add_argument('--query_dirname', default='queries', help='default dirname for query result')

    # query and inf dir ids
    parser.add_argument('-q', '--query_dir_ids', required=True,
                        help='list of query directory ids separated by ","')
    parser.add_argument('-i', '--inf_dir_ids', required=True,
                        help="""
list of infection probas directory ids separated by ","
why this? refer to plot_inference_using_weighted_vs_unweighted.sh""")
    
    parser.add_argument('-n', '--n_queries', type=int, help='number of queries to show')
    parser.add_argument('-s', '--sampling_method', help='')
    parser.add_argument('-l', '--legend_labels',
                        help='list of labels to show in legend separated  by ","')
    parser.add_argument('-f', '--fig_name', help='figure name')

    args = parser.parse_args()

    print("Args:")
    print('-' * 10)
    for k, v in args._get_kwargs():
        print("{}={}".format(k, v))
    
    inf_result_dirname = 'outputs/{}/{}/{}'.format(args.inf_dirname,
                                                   args.data_id,
                                                   args.sampling_method)
    query_dirname = 'outputs/{}/{}/{}'.format(args.query_dirname,
                                              args.data_id,
                                              args.sampling_method)

    print('summarizing ', inf_result_dirname)
    # if n_queries is too large, e.g, 100,
    # we might have no hidden infected nodes left and average precision score is undefined
    n_queries = args.n_queries

    g = load_graph_by_name(args.graph_name)
    
    query_dir_ids = list(map(lambda s: s.strip(), args.query_dir_ids.split(',')))
    if args.legend_labels is not None:
        labels = list(map(lambda s: s.strip(), args.legend_labels.split(',')))
    else:
        labels = query_dir_ids
    print('query_dir_ids:', query_dir_ids)

    inf_dir_ids = list(map(lambda s: s.strip(), args.inf_dir_ids.split(',')))
    print('inf_dir_ids:', inf_dir_ids)
    print('labels:', labels)
    
    cascades = load_cascades('{}/{}'.format(args.cascade_dirname, args.data_id))

    assert n_queries > 0, 'non-positive num of queries'

    if args.eval_method == 'ap':
        eval_func = average_precision_score
    elif args.eval_method == 'auc':
        eval_func = roc_auc_score
    elif args.eval_method == 'precision_at_cascade_size':
        print('precision_at_cascade_size')
        eval_func = precision_at_cascade_size
    else:
        raise NotImplementedError(args.eval_method)
        
    scores_by_method = aggregate_scores_over_cascades_by_methods(
        cascades,
        labels,
        query_dir_ids,
        inf_dir_ids,
        n_queries,
        inf_result_dirname,
        query_dirname,
        eval_func,
        (args.eval_with_mask == 'True'))

    plt.clf()

    fig, ax = plt.subplots(figsize=(5, 4))
    # ax.set_prop_cycle(cycler('color', ['r', 'g', 'b', 'y']) +
    #                   cycler('linestyle', ['-', '--', ':', '-.']) +
    #                   cycler('lw', [4, 4, 4, 4]))

    # print('scores_by_method:', scores_by_method)
    for method in labels:
        assert len(scores_by_method[method]) > 0, 'no scores available for {}'.format(method)
        for r in scores_by_method[method]:
            for i in range(n_queries - len(r)):
                r.append(np.nan)
            assert len(r) == n_queries, "len(r)={}, r={}".format(len(r), r)
        scores = np.array(scores_by_method[method], dtype=np.float32)
        mean_scores = np.nanmean(scores, axis=0)
        # mean_scores = np.mean(scores, axis=0)
        # print(np.std(scores,axis=0))
        ax.plot(mean_scores)
        # ax.hold(True)
    ax.legend(labels, loc='best')
    fig.tight_layout()

    ax.xaxis.label.set_fontsize(20)
    ax.yaxis.label.set_fontsize(20)

    # plt.ylim(0.2, 0.8)
    dirname = 'figs/{}'.format(args.eval_method)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    fig.savefig('figs/{}/{}.pdf'.format(args.eval_method, args.fig_name))

