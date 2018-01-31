#! /bin/zsh

python3 generate_queries.py \
	 -g grqc \
	 -q prediction_error \
	 -n 5 \
	 -s 250 \
	 -m loop_erased \
	 -r pagerank \
	 -c cascade/grqc/ \
	 -d outputs/queries/grqc/test/ \
	 --verbose
