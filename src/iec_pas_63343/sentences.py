# -*- coding: utf-8 -*-
"""
VDES ASM Sentences Module.

This module contains classes and functions for representing, generating [and
parsing] presentation interface sentences compliant with the draft
IEC PAS 63343, dated Oct 2020.

Created on Thu Dec  2 16:59:04 2021

@author: Jan Safar
"""

# =============================================================================
# %% Import Statements
# =============================================================================
# Built-in Modules ------------------------------------------------------------
from math import ceil

# Third-party Modules ---------------------------------------------------------
from bitstring import BitStream

# Local Modules ---------------------------------------------------------------
from iec_61162.part_1.sentences import iec_checksum, iec_ascii_6b_to_8b

# =============================================================================
# %% Helper Functions
# =============================================================================


# =============================================================================
# %% Sentence Definitions
# =============================================================================
class ABBSentence:
    """
    ABB Sentence: ASM broadcast message.

    Parameters
    ----------
    n_sentences : int
        Total number of sentences needed to transfer the message (1-99).
    i_sentence : int
        Sentence number (1-99).
    sequential_id : int
        Sequential message identifier (0-9).
    source_id : int
        Source ID (10 digits as per the draft IEC VDES-ASM PAS; VDES1000
        currently only supports 9 digits).
    channel : int
        AIS channel for broadcast of the message:

        - 0: No preference
        - 1: ASM 1
        - 2: ASM 2
        - 3: Both channels.
    transmission_format : int
        Transmission format:

        - 0: No error coding
        - 1: 3/4 FEC
        - 2: ASM SAT uplink message
        - 3-9: Reserved for future use.
    payload : str
        ASM payload (the Binary Data portion of the message).
    n_fill_bits : int
        Number of fill bits (0-5).
    talker_id : str, optional
        Talker ID. The default is "AI".
    asm_id : str, optional
        ASM message ID as per Rec. ITU-R M.2092. Reserved for future use;
        shall be set to null (""). The default is "".

    """
    formatter_code = "ABB"

    def __init__(
            self,
            n_sentences,
            i_sentence,
            sequential_id,
            source_id,
            channel,
            transmission_format,
            payload,
            n_fill_bits,
            talker_id="AI",
            asm_id=""):

        self.n_sentences = n_sentences
        self.i_sentence = i_sentence
        self.sequential_id = sequential_id
        self.source_id = source_id
        self.channel = channel
        self.transmission_format = transmission_format
        self.payload = payload
        self.n_fill_bits = n_fill_bits
        self.talker_id = talker_id
        self.asm_id = asm_id

    @property
    def string(self):
        """
        Returns
        -------
        s : str
            Sentence string, formatted as per the draft IEC VDES ASM PAS,
            Oct. 2020.

        """
        s = "!{:s}{:s},{:02d},{:02d},{:d},{:s},{:d},{:s},{:d},{:s},{:d}".format(
            self.talker_id,
            self.formatter_code,
            self.n_sentences,
            self.i_sentence,
            self.sequential_id,
            self.source_id if self.source_id == "" else str(self.source_id),
            self.channel,
            self.asm_id,
            self.transmission_format,
            self.payload,
            self.n_fill_bits)

        checksum = iec_checksum(s)
        s += "*" + "{:>02X}".format(checksum) + "\r\n"

        return s


# =============================================================================
# %% Sentence Generation
# =============================================================================
def asm_payload_bs_to_abb_sentences(
        bs,
        sequential_id,
        source_id,
        channel,
        transmission_format,
        talker_id="AI",
        asm_id=""):
    """
    Encapsulate an ASM payload bitstream in an ABB sentence(s).

    TODO: Compare with ais_msg_bs_to_vdm_sentences and see if could be
    consolidated to a single method.

    Parameters
    ----------
    bs : bitstring.BitStream
        ASM payload bitstream (the Binary Data portion of the message).
    sequential_id : int
        Sequential message identifier (0-9).
    source_id : int
        Source ID (10 digits as per the draft IEC VDES-ASM PAS; VDES1000
        currently only supports 9 digits).
    channel : int
        AIS channel for broadcast of the message (0-3).

        - 0: No preference
        - 1: ASM 1
        - 2: ASM 2
        - 3: Both channels.
    transmission_format : int
        Transmission format.

        - 0: No error coding
        - 1: 3/4 FEC
        - 2: ASM SAT uplink message
        - 3-9: Reserved for future use.
    talker_id : str, optional
        Talker ID. The default is "AI".
    asm_id : str, optional
        ASM message ID as per Rec. ITU-R M.2092. Reserved for future use;
        shall be set to null (""). The default is "".

    Returns
    -------
    sentences : list of ABBSentence
        List of ABB sentences encapsulating the ASM payload bitstream.

    """
    n_bits = len(bs)
    n_fill_bits = int((6 - (n_bits % 6)) % 6)

    bs += BitStream(n_fill_bits)

    payload = iec_ascii_6b_to_8b(bs)

    # Split into multiple sentences if necessary and add NMEA/IEC armouring
    i_sentence = 1
    payload_offset = 0
    # Maximum number of characters per payload for the ABB sentence.
    # Assuming the max number of characters per sentence is 82 (as per
    # IEC 61162-1) and that all sentence fields are populated (no null
    # fields) as per the draft IEC PAS for VDES ASM.
    max_payload_char = 42
    n_sentences = ceil(len(payload) / max_payload_char)

    sentences = []
    while i_sentence <= n_sentences:

        # FIXME: n_fill_bits should probably be 0 for all sentences but the
        # last one.
        abb_sentence = ABBSentence(
            n_sentences=n_sentences,
            i_sentence=i_sentence,
            sequential_id=sequential_id,
            channel=channel,
            transmission_format=transmission_format,
            payload=payload[
                payload_offset:(payload_offset + max_payload_char)],
            n_fill_bits=n_fill_bits,
            source_id=source_id,
            talker_id=talker_id,
            asm_id=asm_id)

        i_sentence += 1

        payload_offset += max_payload_char

        sentences += [abb_sentence]

    return sentences


class SentenceGenerator:
    """
    IEC PAS 63343 Sentence Generator.

    For multi-sentence messages, the generator automatically assigns
    an appropriate Sequential ID.

    Parameters
    ----------
    talker_id : str, optional
        Talker ID. The default is "AI".

    """
    def __init__(self, talker_id="AI"):
        self.talker_id = talker_id
        self.abb_sequential_id = 0

    def generate_abb(
            self,
            asm_payload_bs,
            source_id,
            channel,
            transmission_format):
        """
        Generate ABB sentence(s) encapsulating an ASM payload.

        Parameters
        ----------
        asm_payload_bs : bitstring.BitStream
            ASM payload bitstream (the Binary Data portion of an ASM).
        source_id : int
            Source ID (10 digits as per the draft IEC VDES-ASM PAS; VDES1000
            currently only supports 9 digits).
        channel : int
            AIS channel for broadcast of the message (0-3).

            - 0: No preference
            - 1: ASM 1
            - 2: ASM 2
            - 3: Both channels.
        transmission_format : int
            Transmission format.

            - 0: No error coding
            - 1: 3/4 FEC
            - 2: ASM SAT uplink message
            - 3-9: Reserved for future use.

        Returns
        -------
        list of lists of vdes.asm.presentation_layer.sentences.ABBSentence
            List of lists of ABB sentences encapsulating the ASM payload.

        """
        # Generate ABB Sentence(s)
        abb_sentences = asm_payload_bs_to_abb_sentences(
            bs=asm_payload_bs,
            sequential_id=self.abb_sequential_id,
            source_id=source_id,
            channel=channel,
            transmission_format=transmission_format)

        # If this is a multi-sentence message, increase the Sequential ID
        if len(abb_sentences) > 1:
            self.abb_sequential_id = (self.abb_sequential_id + 1) % 10

        return [abb_sentences]


# =============================================================================
# %% Sentence Parsing
# =============================================================================


# =============================================================================
# %% Quick & Dirty Testing
# =============================================================================
if __name__ == "__main__":

    abb_sentence = ABBSentence(
        n_sentences=1,
        i_sentence=1,
        sequential_id=0,
        source_id=111111111,
        channel=1,
        transmission_format=0,
        payload="Beam me up - Scotty",
        n_fill_bits=0)

    print(abb_sentence.string)

    # Sample data
    asm_payload_bs = BitStream("0x123456789ABCDEF"*15)

    # Initialise the Sentence Generator
    sg = SentenceGenerator()

    # Generate some sentences
    sentence_groups = sg.generate_abb(
        asm_payload_bs=asm_payload_bs,
        source_id=111111111,
        channel=1,
        transmission_format=0)

    for group in sentence_groups:
        for sentence in group:
            print(sentence.string)
