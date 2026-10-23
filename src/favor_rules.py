"""Scalar rules for FAVOR-A's documented adapter; not a full search engine."""
from math import sqrt

def exclusion_distance(selectivity, width, mean_d16, mean_d64):
    if not 0 < selectivity <= 1 or width < 1 or not 0 <= mean_d16 <= mean_d64:
        raise ValueError('invalid selectivity, width, or Euclidean anchor distances')
    delta = (mean_d64-mean_d16)/48
    return (1-selectivity)*(width-selectivity)*delta/(2*selectivity*width)

def adjusted_score(squared_distance, eligible, penalty):
    if squared_distance < 0 or penalty < 0:
        raise ValueError('distances must be nonnegative')
    return sqrt(squared_distance)+(0 if eligible else penalty)

def should_stop(min_pending, max_search, search_size, eligible_in_search, width):
    return search_size == width and eligible_in_search/search_size > .5 and min_pending > max_search
