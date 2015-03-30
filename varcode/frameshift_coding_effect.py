# Copyright (c) 2015. Mount Sinai School of Medicine
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Effect annotation for variants which modify the coding sequence and change
reading frame.
"""

from .effects import FrameShift, FrameShiftTruncation, StartLoss, StopLoss
from .mutate import substitute
from .translate import translate

def _frameshift(
        mutated_codon_index,
        sequence_from_mutated_codon,
        variant,
        transcript):
    """
    Determine frameshift effect within a coding sequence (possibly affecting
    either the start or stop codons, or anythign in between)

    Parameters
    ----------
    mutated_codon_index : int
        Codon offset (starting from 0 = start codon) of first non-reference
        amino acid in the variant protein

    sequence_from_mutated_codon: Bio.Seq
        Sequence of mutated cDNA, starting from first mutated codon, until
        the end of the transcript

    variant : Variant

    transcript : transcript
    """

    assert transcript.protein_sequence is not None, \
        "Expect transcript %s to have protein sequence" % transcript

    original_protein_sequence = transcript.protein_sequence

    protein_suffix = translate(
        nucleotide_sequence=sequence_from_mutated_codon,
        first_codon_is_start=False,
        to_stop=True,
        truncate=True)

    if mutated_codon_index == len(original_protein_sequence):
        return StopLoss(
            variant=variant,
            transcript=transcript,
            extended_protein_sequence=protein_suffix)

    # the frameshifted sequence may contain some amino acids which are
    # the same as the original protein!
    n_skip = 0

    for i, new_amino_acid in enumerate(protein_suffix):
        codon_index = mutated_codon_index + i
        if codon_index >= len(original_protein_sequence):
            break
        elif original_protein_sequence[codon_index] != new_amino_acid:
            break
        n_skip += 1

    protein_suffix = protein_suffix[n_skip:]
    aa_pos = mutated_codon_index + n_skip

    # original amino acid at the mutated codon before the frameshift occurred
    aa_ref = original_protein_sequence[aa_pos]

    # TODO: what if all the shifted amino acids were the same and the protein
    # ended up the same length?
    # Add a Silent case
    if len(protein_suffix) == 0:
        # if a frameshift doesn't create any new amino acids, then
        # it must immediately have hit a stop codon
        return FrameShiftTruncation(
            variant=variant,
            transcript=transcript,
            stop_codon_offset=aa_pos,
            aa_ref=aa_ref)
    return FrameShift(
        variant=variant,
        transcript=transcript,
        aa_pos=aa_pos,
        aa_ref=aa_ref,
        shifted_sequence=protein_suffix)

def frameshift_coding_insertion_effect(
        cds_offset_before_insertion,
        inserted_nucleotides,
        sequence_from_start_codon,
        variant,
        transcript):
    """
    Assumption:
        The insertion is happening after the start codon and before the stop
        codon of this coding sequence.
    """

    if cds_offset_before_insertion % 3 == 2:
        # if insertion happens after last nucleotide in a codons
        codon_index_before_insertion = int(cds_offset_before_insertion / 3)
    else:
        # if insertion happens after the 1st or 2nd nucleotide in a codon,
        # then it disrupts that codon
        codon_index_before_insertion = int(cds_offset_before_insertion / 3) - 1

    assert codon_index_before_insertion >= 0, \
        "Expected frameshift_insertion to be after start codon for %s on %s" % (
            variant, transcript)

    original_protein_sequence = transcript.protein_sequence

    assert codon_index_before_insertion < len(original_protein_sequence) - 1, \
        "Expected frameshift_insertion to be before stop codon for %s on %s" % (
            variant, transcript)

    if codon_index_before_insertion == len(original_protein_sequence) - 1:
        # if insertion is into the stop codon then this is a stop-loss
        pass

    cds_offset_after_insertion = (codon_index_before_insertion + 1) * 3
    original_coding_sequence_after_insertion = \
        sequence_from_start_codon[cds_offset_after_insertion:]
    coding_sequence_after_insertion = \
        inserted_nucleotides + original_coding_sequence_after_insertion

    return _frameshift(
        mutated_codon_index=codon_index_before_insertion,
        sequence_from_mutated_codon=coding_sequence_after_insertion,
        variant=variant,
        transcript=transcript)

def frameshift_coding_effect(
        ref,
        alt,
        cds_offset,
        sequence_from_start_codon,
        variant,
        transcript):

    mutated_codon_index = int(cds_offset / 3)

    # TODO: scan through sequence_from_mutated_codon for
    # Kozak sequence + start codon to choose the new start
    if mutated_codon_index == 0:
        return StartLoss(variant=variant, transcript=transcript)

    if len(ref) == 0:
        # treat insertions as a special case since our base-inclusive
        # indexing means something different for insertions:
        #   start = base before insertion
        #   end = base after insertion
        return frameshift_coding_insertion_effect(
            cds_offset_before_insertion=cds_offset,
            inserted_nucleotides=alt,
            sequence_from_start_codon=sequence_from_start_codon,
            variant=variant,
            transcript=transcript)

    # get the sequence starting from the first modified codon until the end
    # of the transcript.
    sequence_after_mutated_codon = \
        sequence_from_start_codon[mutated_codon_index * 3:]

    # the variant's ref nucleotides should start either 0, 1, or 2 nucleotides
    # into `sequence_after_mutated_codon`
    offset_into_mutated_codon = cds_offset % 3

    sequence_from_mutated_codon = substitute(
        sequence=sequence_after_mutated_codon,
        offset=offset_into_mutated_codon,
        ref=ref,
        alt=alt)

    return _frameshift(
        mutated_codon_index=mutated_codon_index,
        sequence_from_mutated_codon=sequence_from_mutated_codon,
        variant=variant,
        transcript=transcript)
