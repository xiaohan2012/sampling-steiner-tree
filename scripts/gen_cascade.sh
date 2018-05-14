#! /bin/zsh

graph="grqc-sto"
n_cascades=96
n_observation_rounds=1
# n_cascades=8
# n_observation_rounds=1
cascade_model="ic"
graph_suffix=" "

obs_method="uniform"
obs_fraction=0.2

# works for IC
min_size=100
max_size=1000

# works for SI
cascade_fraction=0.025
dataset_id="${graph}-m${cascade_model}-s${cascade_fraction}-o${obs_fraction}-om${obs_method}"

ourput_dir="cascade-weighted/${dataset_id}"
from_cascade_dir="cascade-weighted/${graph}-m${cascade_model}-s${cascade_fraction}-o${obs_fraction}-ombfs-head"

print "ouput to ${ourput_dir}"

python3 simulate_cascades.py \
	-g ${graph} \
	-c ${from_cascade_dir} \
	-n ${n_cascades} \
	-o ${obs_fraction} \
	-f ${graph_suffix} \
	--n_observation_rounds ${n_observation_rounds} \
	--use_edge_weights \
	-m ${cascade_model} \
	-d ${ourput_dir} \
	-s ${cascade_fraction} \
	--observation_method ${obs_method} \
	--min_size ${min_size} \
	--max_size ${max_size}
