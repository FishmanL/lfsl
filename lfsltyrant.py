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

class Lfsltyrant(Peer):
    # constants for how fast we update our beliefs about upload and download speeds

    def post_init(self):
        print "post_init(): %s here!" % self.id
        # track beliefs about uploading (sum of upload bandwidth for the first r rounds and then updated based on choking)
        self.upload_beliefs = dict()
        # track both download sums (sum of downloaded blocks) and download beliefs (alpha/gamma)
        self.download_nums = dict()
        self.download_beliefs = dict()

        # dictionary mapping peer ids to array of r booleans (whether j has unchoked us in each of the last r rounds)
        self.unchoking_beliefs = dict()
        self.we_unchoked = []

        self.gamma = 0.1
        self.r = 3
        self.alpha = 0.2


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
        if round == 0:
            self.initialize_beliefs(peers)
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
            if round >= self.r:
                for piece_id in ilist[:n]:  #rarest first
                    # aha! The peer has this piece! Request it.
                    # which part of the piece do we need next?
                    # (must get the next-needed blocks in order)
                    start_block = self.pieces[piece_id]
                    req = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(req)
            else:
                for piece_id in random.sample(isect, n):
                    # aha! The peer has this piece! Request it.
                    # which part of the piece do we need next?
                    # (must get the next-needed blocks in order)
                    start_block = self.pieces[piece_id]
                    req = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(req)
        return requests

    def initialize_beliefs(self, peers):
        logging.debug('initializing')
        logging.debug(str(peers))
        for peer in peers:
            self.download_beliefs[peer.id] = 1
            self.upload_beliefs[peer.id] = 1
            self.unchoking_beliefs[peer.id] = []

    # update beliefs based on past round
    def update_beliefs(self, peers, history,
                        update_download_sum=True,
                        update_upload_sum=False,
                        update_unchoking=True,
                        update_beliefs=True):
        round = history.current_round()
        last_downloads = history.downloads[round - 1]
        last_uploads = history.uploads[round - 1]
        # update number of blocks I have downloaded from everybody
        if update_download_sum:
            for download in last_downloads:
                if download.from_id in self.download_nums.keys():
                    self.download_nums[download.from_id] += download.blocks
                else:
                    self.download_nums[download.from_id] = download.blocks
        # update number of blocks I have uploaded from everybody, only called in the first r rounds
        if update_upload_sum:
            for upload in last_uploads:
                # track who unchoked us
                self.upload_beliefs[upload.to_id] += upload.bw

        if update_unchoking:
            # update list of whether j unchoked us in the last r periods
            unchoked = set(download.from_id for download in last_downloads)
            for peer in peers:
                self.unchoking_beliefs[peer.id].append(peer.id in unchoked)
                while len(self.unchoking_beliefs[peer.id]) > self.r:
                    self.unchoking_beliefs[peer.id].pop(0)

        if update_beliefs:
            # update list of whether we unchoked them
            we_unchoked = set(upload.to_id for upload in last_uploads)
            for pid in we_unchoked:
                # if they didn't unchoke us, increase the upload belief
                if not self.unchoking_beliefs[pid][-1]:
                    self.upload_beliefs[pid] *= (1 + self.alpha)
                # if they did unchoke us, change the download belief to the download speed
                else:
                    self.download_beliefs[pid] = self.download_nums[pid]
                if sum(self.unchoking_beliefs[pid]) == 3:
                    self.upload_beliefs[pid] *= (1 - self.gamma)
        logging.debug('Download beliefs for %s %s' % (self.id, str(self.download_nums)))
        logging.debug('last downloads %s', str(last_downloads))
        logging.debug('Upload beliefs for %s %s' % (self.id, str(self.upload_beliefs)))
        logging.debug('Unchoking beliefs for %s %s' % (self.id, str(self.unchoking_beliefs)))

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
        # update beliefs by aggregating upload/download speeds for the first few rounds
        if round > 0:
            if round < self.r:
                self.update_beliefs(peers, history, update_download_sum = True, update_upload_sum = True, update_beliefs = False)
                for key, value in self.download_nums.iteritems():
                    self.download_beliefs[key] = value
            else:
                self.update_beliefs(peers, history)
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading using brain cells")
            # if it has been fewer than r rounds, we allocate evenly among everyone
            if round < self.r:
                logging.debug('even split')
                chosen = [request.requester_id for request in requests]
                bws = even_split(self.up_bw, len(chosen))
            # if it has been r or more rounds, we can use the algorithm
            else:
                # change my internal state for no reason
                cap = self.up_bw
                # sort requesters by calculating ratios of download to upload beliefs and sorting by decreasing
                ratios = dict()
                requesters = [request.requester_id for request in requests]
                for requester in requesters:
                    logging.debug('download_beliefs' + str(self.download_beliefs))
                    logging.debug(self.download_beliefs[requester])
                    logging.debug(self.upload_beliefs[requester])
                    ratios[requester] = self.download_beliefs[requester] * 1.0 / self.upload_beliefs[requester]

                ratios_sorted = sorted(ratios.items(), key = lambda x: x[1], reverse = True)
                bandwidth_used = 0
                chosen, bws = [], []
                for pid, ratio in ratios_sorted:
                    if self.upload_beliefs[pid] + bandwidth_used > self.up_bw:
                        break
                    else:
                        bws.append(self.upload_beliefs[pid])
                        bandwidth_used += self.upload_beliefs[pid]
                        chosen.append(pid)
                self.we_unchoked = chosen
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
