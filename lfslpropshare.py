#!/usr/bin/python

"""
The PropShare client allocates upload bandwidth based on the downloads received from
peers in the previous round: It calculates what share each peer contributed to the total
download and allocates its own bandwidth proportionally. In addition it reserves a small
share of its bandwidth for optimistic unchoking (e.g., 10%). For example

"""

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class Lfslpropshare(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.reserved_for_optimistic = 0.1
        self.for_sharing = 1-self.reserved_for_optimistic
    
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
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        round = history.current_round()
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            if isect == set():
                continue
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
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
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            if round == 0:
                chosen = [request.requester_id for request in requests][:4]
                bws = even_split(self.up_bw, len(chosen))
            else:
                ndict = {}
                for i in range(1, min(round, 4)):
                    pasthist = history.downloads[round - i]

                    for item in pasthist:
                        if item.to_id != self.id or 'Seed' in item.from_id:
                            continue
                        pid = item.from_id
                        if pid in ndict.keys():
                            ndict[pid] += item.blocks
                        else:
                            ndict[pid] = item.blocks
                requestids = [request.requester_id for request in requests]
                totaluploads = sum([ndict.get(id, 0) for id in requestids])
                #now actually find the proportionality
                try:
                    bws = [int(self.up_bw*self.for_sharing*(float(ndict.get(id, 0))/float(totaluploads))) for id in requestids]
                    randind = random.randint(0, len(requestids) - 1)

                    to_share = min(self.up_bw - sum(bws), self.up_bw*self.for_sharing)
                    #the rest of our bandwidth goes towards optimistic unchoking
                    bws[randind] += int(to_share)
                    logging.debug((str(self.id) + " " + str(self.up_bw) + ": " + str(zip(requestids,bws))))
                    chosen = requestids
                except:
                    chosen = [request.requester_id for request in requests][:4]
                    bws = even_split(self.up_bw, len(chosen))



        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
