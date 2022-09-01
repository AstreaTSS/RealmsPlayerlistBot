import rapidfuzz
from rapidfuzz import fuzz
from rapidfuzz import process


def extract_from_list(
    argument,
    list_of_items,
    processors,
    score_cutoff=0.8,
    scorers=None,
):
    """Uses multiple scorers and processors for a good mix of accuracy and fuzzy-ness"""
    if scorers is None:
        scorers = [rapidfuzz.distance.JaroWinkler.similarity]
    combined_list = []

    for scorer in scorers:
        for processor in processors:
            if fuzzy_list := process.extract(
                argument,
                list_of_items,
                scorer=scorer,
                processor=processor,
                score_cutoff=score_cutoff,
            ):
                combined_entries = [e[0] for e in combined_list]
                new_members = [e for e in fuzzy_list if e[0] not in combined_entries]
                combined_list.extend(new_members)

    return combined_list
