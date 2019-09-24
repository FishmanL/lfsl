#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

gamma = 0.1
r = 3
alpha = 0.2

class Lfsltyrant(Peer):
    # constants for how fast we update our beliefs about upload and download speeds

    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        # initialize beliefs about upload and download speeds and whether they have unchoked in the last 3 periods between each agent
        self.beliefs = dict()

    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        # count number of peers that have each needed piece
        piecedict = {}
        for piece in needed_pieces:
            numhaving = 0
            for peer in peers:
                if piece in peer.available_pieces:
                    numhaving += 1
            piecedict[piece] = numhaving

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # Sort peers by id.  This is probably not a useful sort, but other
        # sorts might be useful
        random.shuffle(peers)
        round = history.current_round()
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            if isect==set():
                continue
            n = min(self.max_requests, len(isect))

            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            # in first 5 rounds, request pieces randomly
            # after that, look for rarest pieces first
            # sort by which pieces are rarer
            ilist = sorted(isect, key = lambda x: piecedict[x])
            if round >= 5:
                for piece_id in ilist[:n]:  #rarest first
                    # aha! The peer has this piece! Request it.
                    # which part of the piece do we need next?
                    # (must get the next-needed blocks in order)
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
            else:
                for piece_id in random.sample(isect, n):
                    # aha! The peer has this piece! Request it.
                    # which part of the piece do we need next?
                    # (must get the next-needed blocks in order)
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # if it has been fewer than r rounds, we allocate evenly among everyone
            if round < r:
                chosen = [request.requester_id for request in requests]
                bws = even_split(self.up_bw, len(chosen))
            # once it has been r rounds, we can create our initial beliefs about each peer based on the history
            elif round == r:
                # make dictionaries with total download and upload bandwith for each agent
                downloads_peer = {}
                for round_downloads in history.downloads:
                    for download in round_downloads:
                        if download.from_id in downloads_peer.keys():
                            downloads_peer[download.from_id] = download.blocks
                        else:
                            downloads_peer[download.from_id] += download.blocks
                    logging.debug("Here's my download dictionary.")
                    logging.debug(str(downloads_peer))
            else:
                # if it has been more than r rounds, we allocate based on the algorithm
                # change my internal state for no reason
                self.dummy_state["cake"] = "pie"
                request = random.choice(requests)
                chosen = [request.requester_id]
                # Evenly "split" my upload bandwidth among the one chosen requester
                # ALLOCATE UIJ BASED ON SELF.BELIEFS U_IJ
                bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
