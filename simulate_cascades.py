import os
import pickle
import argparse
from graph_helpers import load_graph_by_name
from experiment import gen_inputs_varying_obs
from tqdm import tqdm
from root_sampler import build_out_degree_root_sampler


parser = argparse.ArgumentParser(description='')
parser.add_argument('-g', '--graph', required=True, help='graph name')
parser.add_argument('-f', '--graph_suffix', default='', help='suffix of graph path')

parser.add_argument('-n', '--n_cascades', type=int, default=12,
                    help='number of cascades')
parser.add_argument('--n_observation_rounds', type=int, default=8,
                    help='number of rounds on observation repeated for each cascade')

parser.add_argument('-o', '--obs_fraction', type=float, default=0.2,
                    help='fraction of observed  nodes')
parser.add_argument('-d', '--output_dir', default='cascade',
                    help='output directory')

# the following applicable to real cascades
parser.add_argument('-c', '--cascade_path',
                    help='cascade path (applicable if the cascade is given)')

# the following applicable to simulated cascades
parser.add_argument('-m', '--cascade_model', type=str, default='si',
                    choices=('si', 'ic'),
                    help='cascade model')
parser.add_argument('-s', '--stop_fraction', type=float, default=0.5,
                    help='fraction of infected nodes to stop')
parser.add_argument('-p', '--infection_proba', type=float, default=0.5,
                    help='infection probability')
parser.add_argument('--min_size', type=int, default=10,
                    help='minimum cascade size (applicable for IC model)')
parser.add_argument('--max_size', type=int, default=10,
                    help='maximum cascade size (applicable for IC model)')
parser.add_argument('-w', '--use_edge_weights', action='store_true',
                    help="""flag on using random edge probability.
If ON, edge weight is sampled uniformly from [p_min, p_max]""")

parser.add_argument('--observation_method', type=str, choices=('uniform', 'leaves', 'late'),
                    help='how infections are observed')


args = parser.parse_args()

print("Args:")
print('-' * 10)
for k, v in args._get_kwargs():
    print("{}={}".format(k, v))

graph_name = args.graph

if not args.use_edge_weights:
    print('uniform edge weight')
    g = load_graph_by_name(graph_name, weighted=False, suffix=args.graph_suffix)
    p = args.infection_proba
else:
    print('non-uniform edge weight')
    g = load_graph_by_name(graph_name, weighted=True, suffix=args.graph_suffix)
    p = g.edge_properties['weights']

print('p=', p)
print('p.a=', p.a)

root_sampler = build_out_degree_root_sampler(g)

d = args.output_dir
if not os.path.exists(d):
    os.makedirs(d)

for i in tqdm(range(args.n_cascades)):
    iters = gen_inputs_varying_obs(
        g,
        source=root_sampler(),
        cascade_path=args.cascade_path,
        stop_fraction=args.stop_fraction,
        q=args.obs_fraction,
        p=p,
        model=args.cascade_model,
        observation_method=args.observation_method,
        min_size=args.min_size,
        max_size=args.max_size,
        n_times=args.n_observation_rounds,
        return_tree=(args.observation_method == 'leaves'))
    
    for j, (obs, c, tree) in enumerate(iters):
        id_ = args.n_observation_rounds * i + j
        path = os.path.join(d, '{}.pkl'.format(id_))
        pickle.dump((obs, c), open(path, 'wb'))
