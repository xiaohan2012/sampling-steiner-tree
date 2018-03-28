import random
import numpy as np
from tqdm import tqdm
from core import uncertainty_scores
from graph_tool.centrality import pagerank
from graph_helpers import extract_nodes
from root_sampler import build_root_sampler_by_pagerank_score, build_true_root_sampler


class NoMoreQuery(Exception):
    pass


class BaseQueryGenerator():
    def __init__(self, g, obs=None, c=None, verbose=False, **kwargs):
        self.g = g
        if obs is not None:
            self.receive_observation(obs, c)
        else:
            self._cand_pool = None

        self.verbose = verbose

    def receive_observation(self, obs, c):
        self._cand_pool = set(extract_nodes(self.g)) - set(obs)

    def update_observation(self, g, inf_nodes, q, label, c):
        pass

    def select_query(self, *args, **kwargs):
        if len(self._cand_pool) == 0:
            raise NoMoreQuery()
        
        q = self._select_query(*args, **kwargs)
        self._cand_pool.remove(q)
        return q

    def _select_query(self, *args, **kwargs):
        raise NotImplementedError('do it yourself!')

    def update_pool(self, g):
        """some nodes might be removed from g, thus they are not selectble from self._cand_pool
        """
        visible_nodes = set(extract_nodes(g))
        self._cand_pool = list(set(self._cand_pool).intersection(visible_nodes))

    def empty(self):
        return len(self._cand_pool) == 0


class RandomQueryGenerator(BaseQueryGenerator):
    """random query generator"""

    def _select_query(self, *args, **kwargs):
        return random.choice(list(self._cand_pool))


class PRQueryGenerator(BaseQueryGenerator):
    """rank node by pagerank score
    """
    def _update_pagerank_score(self, g, obs):
        pers = self.g.new_vertex_property('float')
        for o in obs:
            pers[o] = 1 / len(obs)
        rank = pagerank(self.g, pers=pers)

        self.pr = {}
        for v in self.g.vertices():
            self.pr[int(v)] = rank[v]

        for o in obs:
            self.pr[int(o)] = 0
            
    def receive_observation(self, obs, c):
        # personalized vector for pagerank
        # print('START: pagerank')
        self._update_pagerank_score(self.g, obs)

        # print('DONE: pagerank')
        super(PRQueryGenerator, self).receive_observation(obs, c)

    def update_observation(self, g, inf_nodes, node, label, c):
        self._update_pagerank_score(g, inf_nodes)

    def _select_query(self, *args, **kwargs):
        return max(self._cand_pool, key=self.pr.__getitem__)


class SamplingBasedGenerator(BaseQueryGenerator):
    def __init__(self, g, sampler, *args, root_sampler=None, error_estimator=None,
                 root_sampler_eps=0.0,
                 **kwargs):
        self.sampler = sampler
        assert root_sampler in {'random', 'pagerank', 'true_root'}

        self.root_sampler_name = root_sampler
        self.root_sampler_eps = root_sampler_eps

        # print('self.root_sampler_name', self.root_sampler_name)
        self.error_estimator = error_estimator
        super(SamplingBasedGenerator, self).__init__(g, *args, **kwargs)

    def _update_root_sampler(self, obs, c, **kwargs):
        # print('START: sampler.fill')
        if self.root_sampler_name == 'pagerank':
            try:
                self.root_sampler = build_root_sampler_by_pagerank_score(
                    self.g, obs, c, self.root_sampler_eps)
            except ValueError as e:
                raise NoMoreQuery from e
        elif self.root_sampler_name == 'true_root':
            self.root_sampler = build_true_root_sampler(c)
            # raise NotImplementedError('to do bro')
        elif self.root_sampler_name == 'random':
            self.root_sampler = None  # equivalent to 'random'

    def receive_observation(self, obs, c, **kwargs):
        self._update_root_sampler(obs, c, **kwargs)

        self.sampler.fill(obs,
                          root_sampler=self.root_sampler)
        # add samples to error estimator
        self.error_estimator.build_matrix(self.sampler.samples)
        
        # print('DONE: sampler.fill')
        super(SamplingBasedGenerator, self).receive_observation(obs, c)

    def update_observation(self, g, inf_nodes, node, label, c):
        """update the tree samples"""
        # rigorously speaking,
        # root sampler should be updated, for example
        # earliet node might be updated, or uninfected nodes get removed
        # print('update observation, self.root_sampler', self.root_sampler)
        self._update_root_sampler(inf_nodes, c)
        new_samples = self.sampler.update_samples(inf_nodes, node, label,
                                                  root_sampler=self.root_sampler)
        self.error_estimator.update_trees(new_samples, node, label)


class EntropyQueryGenerator(SamplingBasedGenerator):
    def __init__(self, g, *args,
                 **kwargs):
        super(EntropyQueryGenerator, self).__init__(g, *args, **kwargs)

    def _select_query(self, g, inf_nodes):
        # need to resample the spanning trees
        # because in theory, uninfected nodes can be removed from the graph
        scores = uncertainty_scores(
            g, inf_nodes,
            self.sampler,
            self.error_estimator)
        q = max(self._cand_pool, key=scores.__getitem__)
        return q


class PredictionErrorQueryGenerator(SamplingBasedGenerator):
    """OUR CONTRIBUTION"""
    def __init__(self, *args,
                 prune_nodes=False,
                 n_node_samples=None,
                 **kwargs):
        """
        n_node_samples: number of nodes used to estimate probabilities
        pass None if using all of them.
        """
        self.min_proba = kwargs.get('min_proba', 0.0)
        self.n_node_samples = n_node_samples
        self.prune_nodes = prune_nodes

        super(PredictionErrorQueryGenerator, self).__init__(*args, **kwargs)

    def prune_candidates(self):
        self._cand_pool = set(
            self.error_estimator.filter_out_extreme_targets(
                self._cand_pool,
                min_value=self.min_proba))

    def _sample_nodes_for_estimation(self):
        # use node samples to estimate prediction error
        cand_node_samples = list(self._cand_pool)
        node_sample_inf_proba = self.error_estimator.unconditional_proba(cand_node_samples)
        # node_sample_inf_proba = np.array(
        #     [len(matching_trees(self.sampler.samples, n, 1)) / len(self.sampler.samples)
        #      for n in cand_node_samples])

        # the closer to 0.5, the better
        val1 = node_sample_inf_proba * 2
        val2 = (1 - node_sample_inf_proba) * 2
        sampling_weight = np.where(val1 < val2, val1, val2)  # take the pairwise minimum
        assert (sampling_weight <= 1).all()

        sampling_weight /= sampling_weight.sum()

        return np.random.choice(cand_node_samples, self.n_node_samples,
                                p=sampling_weight)
        
    # @profile
    def _select_query(self, g, inf_nodes):
        if self.prune_nodes:
            # pruning nods that are sure to be infected/uninfected
            # also, we can set a real-valued threshold
            if self.verbose:
                prev_n = len(self._cand_pool)
                
            self.prune_candidates()  #  _cand_pool updated

            if self.verbose:
                print('pruning candidates from {} to {}'.format(
                    prev_n, len(self._cand_pool)))
        elif self.verbose:
            print('there is no candidate pruning: #candidates={}'.format(len(self._cand_pool)))
                            
        if ((self.n_node_samples is None) or self.n_node_samples >= len(self._cand_pool)):

            if self.verbose:
                print('no estimation node sampling')

            node_samples = self._cand_pool
        else:
            node_samples = self._sample_nodes_for_estimation()

            if self.verbose:
                print('number of estimation nodes'.format(len(node_samples)))

        def score(q):
            nodes = set(node_samples) - {q}
            if len(nodes) == 0:
                return float('inf')  # throw this node away
            else:
                return self.error_estimator.query_score(
                    q, nodes)

        q2score = {}
        # for q in tqdm(self._cand_pool)
        for q in self._cand_pool:
            q2score[q] = score(q)
        
        # import pickle as pkl
        # import tempfile
        # with tempfile.NamedTemporaryFile(dir='./tmp', delete=False) as f:
        #     probas = {n: p for n, p in zip(
        #         list(self._cand_pool),
        #         self.error_estimator.unconditional_proba(list(self._cand_pool)))}
        #     pkl.dump((q2score, probas), f)
        #     f.flush()
        #     print('flushed')
            
        # top = 10
        # top_qs = list(sorted(q2score, key=q2score.__getitem__))[:top]

        # print('top score queries:')
        # for q in top_qs:
        #     print('{}({:.2f})'.format(q, q2score[q]))

        # changed to max
        # best_q = max(self._cand_pool, key=q2score.__getitem__)
        if len(self._cand_pool) == 0:
            raise NoMoreQuery

        best_q = min(self._cand_pool, key=q2score.__getitem__)
        # print('best_q', best_q)
        return best_q
