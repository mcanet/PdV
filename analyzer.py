#!/usr/bin/env python
# encoding: utf-8
"""
Analyze votes from a tsv file, perform some functions, cluster the voters in
groups, possible reorder the groups, etc.

Fast prototype ;)

Authors:
    Chris Hager
    Jaume Nualart
"""

__version__ = "0.1"

from operator import itemgetter
import sys
import os
import pprint
import time
import shutil
from optparse import OptionParser

import kmeans
import gridgrouper

# Modes map to the column of the votes-tsv file to use
MODE_VOTE_RESULT = 4
MODE_VOTE_SPEED = 5


class Analyzer(object):
    """
    This class is able to read a tsv file with the votes, and perform various
    related functions.
    """
    def __init__(self, fn, abstention_id):
        # 'None' to count as abstention, any string to add to another vote
        self.abstention_id = abstention_id

        # Read the votes tsv file
        f = open(fn)
        self.data = [i.strip().split() for i in f.readlines()]
        if self.data[0][0] == "seatid":
            del self.data[0]

        # Read map.tsv and build internal representations
        f = open("C:\\PdV\\data\\map.tsv")
        self.map_xy = {}
        self.map_keypad = {}
        for i in f.readlines():
            seat_id, keypad_id, x, y, x_px, y_px, section, group, type, active, gender = i.strip().split()
            #print seat_id
            #print "vvvvvvvvvvvvvvvvvvv"
            if keypad_id == "keypadid":
                continue
            seat_id = int(seat_id)
            x = int(x)
            y = int(y)
            self.map_xy[(x, y)] = [seat_id, keypad_id, x, y, x_px, y_px, section, group, type, active, gender]
            self.map_keypad[keypad_id] = [seat_id, keypad_id, x, y, x_px, y_px, section, group, type, active, gender]
        #### TODO
        #print "--------------"
        #print self.map_keypad
        #sys.exit()
        #pprint.pprint(self.map_dict)

    def kmeans(self, sums, num_clusters=3):
        # calculate kmeans with simplified data
        data = []
        for voter in sums.keys():
            data.append([voter, sums[voter][-1]])
        return kmeans.kmeans(data, num_clusters)

    def grid_reorder(self, clusters, gridsize="31x6"):
        # prepare for gridgrouper (only count size of groups)
        groups = []
        for cluster in clusters:
            groups.append(len(clusters[cluster]))

        grid, groups = gridgrouper.build_grid(gridsize, groups)

        # Map the new seat positions to the clusters
        seats_info = {}
        group = 0
        for cluster in clusters:
            for i in xrange(len(clusters[cluster])):
                keypad, oldsum = clusters[cluster][i]
                seat = groups[group].seats[i]
                seats_info[keypad] = [seat.x, seat.y, group]
            group += 1

        return grid, groups, seats_info

    def remap_after_reorder(self, seats_info):
        """
        Map the regrouped voters back to the original map.tsv (theater seats mapping)
        """
        #print "fffff"
        #print seats_info
        # Build new map: replace keypad_id and group in original map based
        # on the x/y coordinates.
        map_new = []
        for keypad_id in seats_info:
            # Extract new pos info from the clusters
            x_new, y_new, group_new = seats_info[keypad_id]

            # Extract info from original map
            seat_id, keypad_id_old, x, y, x_px, y_px, section, group, type, active, gender =\
            self.map_xy[(x_new, y_new)]

            # Combine info into map_new
            map_new.append([seat_id, keypad_id, x, y, x_px, y_px, section, group_new, type, active, gender])

        return map_new

    def read_votes_tsv(self, mode=MODE_VOTE_RESULT):
        """
        Reades the raw votes tsv file and builds the internal data structure.

        voters is a dictionary of keypad-id mapping to a dictionary of
        voting-round-id and this keypads respective votes:

            {'1': {'Judge20111210053447': '1',
               'Judge20111210053457': '2',
               'Judge20111210053509': '1',
               'Judge20111210053516': '2',
               'Judge20111210053524': '1',
               'Judge20111210053531': '2'},
              ...

        voters_simple is a dictionary of keypad-id mapping to a list of only the results of this
        keypads votations:

            {'1': ['1', '2', '1', '2', '1', '2'],
             '10': ['2', '1', '2', '2', '1', '2'],
             ...
        """
        voters = {}
        voters_simple = {}
        votation_ids = []
        for l in self.data[1:]:
            #print l
            # Build the list of votation ids
            if l[0] not in votation_ids:
                votation_ids.append(l[0])
            # Add vote of this voter. If not yet exists, create empty
            if l[3] not in voters:
                voters[l[3]] = {}

            # Save the respective column of the tsv file into our data structure
            value = l[mode]

            # If analizing by voting speed, we convert to float
            if mode == MODE_VOTE_SPEED:
                value = float(value) if value else 0

            # Store the value we want to analyze
            voters[l[3]][l[0]] = value

        # Fill up absent votes and build list
        for v in voters.keys():
            for vid in votation_ids:
                if not vid in voters[v]:
                    voters[v][vid] = self.abstention_id if mode == MODE_VOTE_RESULT else 0
                if not v in voters_simple:
                    voters_simple[v] = []
                voters_simple[v].append(voters[v][vid])

        self.votation_ids = votation_ids
        return voters, voters_simple

    def voting_correlatation_sums(self, voters):
        """
        Build the sums of how many other people voted the same.
        """
        votecounts = []
        for i in xrange(len(self.votation_ids)):
            # For each votation, sum up all votes we can find
            c = {}
            for voter in voters.keys():
                vote = voters[voter][i]
                if not vote in c:
                    c[vote] = 1
                else:
                    c[vote] += 1
            votecounts.append(c)

        print "Summary: vote count per votation"
        #pprint.pprint(votecounts)
        print

        # Replace votes with sum of people with same vote
        voters_sums = {}
        for voter in voters.keys():
            voters_sums[voter] = []
            for i in xrange(len(voters[voter])):
                vote = voters[voter][i]
                voters_sums[voter].append(int(votecounts[i][vote]) - 1)
            voters_sums[voter].append(sum(voters_sums[voter]))

        return voters_sums


def analyze(mode, reorder, num_groups, abstention_id=None):
    """
    Analyzes the votes, groups them with k-means and optionally reorders the seats.
    """
    # Load data from tsvº
    analyzer = Analyzer("C:\\PdV\\data-tmp\\allkey.tsv", abstention_id)
    voters, voters_simple = analyzer.read_votes_tsv(mode)

    # Prepare data for k-means clustering
    if mode == MODE_VOTE_RESULT:
        data = analyzer.voting_correlatation_sums(voters_simple)

    elif mode == MODE_VOTE_SPEED:
        # build the averages of the voting speed in each round, per participant
        data = {}
        for voter in voters_simple:
            data[voter] = [sum(voters_simple[voter])/len(voters_simple[voter])]

    # Build clusters by kmeans
    means, clusters = analyzer.kmeans(data, num_clusters=num_groups)

    # Lots of output of the means
    print "means:"
    pprint.pprint(means)

    print
    print "Number of people in each cluster: "
    print [len(clusters[key]) for key in clusters]
    print

    for group_id in clusters:
        if group_id >= len(means):
            s = "> %s" % means[group_id-1]
        else:
            s = "< %s" % means[group_id]
        print "  %s people %s" % (len(clusters[group_id]), s)

    # Update the original map with the calculated group, and if reordering with
    # the new keypad-id.
    map_new = None
    if reorder:
        # Regroup and remap
        grid, groups, seats_info = analyzer.grid_reorder(clusters)
        print; grid.show()

        map_new = analyzer.remap_after_reorder(seats_info)

    else:
        # Just update the original map with the calculated group for each keypad.
        map_new = []
        for group_id in clusters:
            for keypad_id, _ in clusters[group_id]:
                # Extract info from original map
                seat_id, keypad_id_old, x, y, x_px, y_px, section, group, type, active, gender =\
                        analyzer.map_keypad[keypad_id]

                # Combine info into map_new
                map_new.append([seat_id, keypad_id, x, y, x_px, y_px, section, group_id, type, active, gender])

    print
    print "Updated Map 1" + \
          "(seat-id, new-keypad-id, x, y, x_px, y_px, active, theater-group, vote-group)"
    return map_new

def analyze_simpleMar(abstention_id=None):
    """
    Analyzes the votes, groups them with k-means and optionally reorders the seats.
    """
    # Load map
    data2 = open("C:\\PdV\\data\\map.tsv")
    map_orig = [i.strip().split() for i in data2.readlines()]
    oldfalse_kp = []
    for i in map_orig:
        if is_number(i[0]):
            if i[9] == "false":
                oldfalse_kp.append(str(i[1]))
		
    # Load data from tsv
    analyzer = Analyzer("C:\\PdV\\data-tmp\\allkey.tsv", abstention_id)
    voters, voters_simple = analyzer.read_votes_tsv(MODE_VOTE_RESULT)
    data = analyzer.voting_correlatation_sums(voters_simple)

    # Sort votes/keypads by sum of correlations
    s = sorted(data.items(), key=lambda (k, v): v[-1])
    print "abans:"
    print len(s)
    #Clean false votes
    sTemp =[] 
    for i in range(0, len(s)):
        if not str(s[i][0]) in oldfalse_kp:
            sTemp.append(s[i])
    s = sTemp
    print "despres:"
    print len(s)
    
	
    # Extract a simple version of map
    map_new_tmp = []
    for keypad_id in analyzer.map_keypad:
        if not str(keypad_id) in oldfalse_kp:
            map_new_tmp.append(analyzer.map_keypad[keypad_id])
            map_new_tmp.sort()
    print "----------------"

	
	# mar: maybe not need or wrong
    # Just update the original map with the calculated group for each keypad.
    map_new = []
    cnt = 1
    for seat_id, keypad_id_old, x, y, x_px, y_px, section, group, type, active, gender in map_new_tmp:
        # Combine info into map_new
        map_new.append([cnt,s[cnt][0] , x, y, x_px, y_px, section, group, type, active, gender])
        cnt += 1
        if cnt >= len(s):
            break
    #print len(analyzer.map_keypad)
    
    print "Updated Map (simple1)" +\
          "(seat-id, new-keypad-id, x, y, x_px, y_px, section, group, type, active, gender)"
    #map_new.sort()
	
    # Fill it up de map:
	# adding active = block for every second keypad
   
    
    # Mar: Add append to false in map with no votes
    
    for i in map_orig:
        if is_number(i[0]):
            if i[9] == "false":
                #i[0] = int(i[0])
                i[0] = int(cnt)
                map_new.append(i)
                cnt += 1
    			
    map_new.sort(key=itemgetter(0))
    #pprint.pprint(map_new)
    

	#print oldfalse_kp
    for line in map_new:
        if is_number(line[0]):
            if not int(line[0]) % 2:
                line[9] = "block"
            else:
                line[9] = "true"
				
    # Mar: write false if was before
	
    for line in map_new:
        if is_number(line[0]):
            if str(line[1])  in oldfalse_kp:
                # Put action=false to the empty seats in old map.
                line[9] = "false"

    pprint.pprint(map_new)
    #print "maaaaaaaaaaaaaaap"
    #sys.exit()
    return map_new

def analyze_simple(abstention_id=None):
    """
    Analyzes the votes, groups them with k-means and optionally reorders the seats.
    """
    # Load data from tsv
    analyzer = Analyzer("C:\\PdV\\data-tmp\\allkey.tsv", abstention_id)
    voters, voters_simple = analyzer.read_votes_tsv(MODE_VOTE_RESULT)
    data = analyzer.voting_correlatation_sums(voters_simple)

    # Sort votes/keypads by sum of correlations
    s = sorted(data.items(), key=lambda (k, v): v[-1])

    # Extract a simple version of map
    map_new_tmp = []
    for keypad_id in analyzer.map_keypad:
        map_new_tmp.append(analyzer.map_keypad[keypad_id])
    # TODO map_new_tmp.sort()
    #print "----------------"
    #pprint.pprint(map_new_tmp)
    #print len(analyzer.map_keypad)
    #sys.exit()

    # Just update the original map with the calculated group for each keypad.
    map_new = []
    cnt = 0
    for seat_id, keypad_id_old, x, y, x_px, y_px, section, group, type, active, gender in map_new_tmp:
        # Combine info into map_new
        map_new.append([seat_id, s[cnt][0], x, y, x_px, y_px, section, group, type, active, gender])
        cnt += 1
        if cnt >= len(s):
            break

    print "Updated Map (simple1)" +\
          "(seat-id, new-keypad-id, x, y, x_px, y_px, section, group, type, active, gender)"
    # TODO map_new.sort()
    # Fill it up de map:
    data2 = open("C:\\PdV\\data\\map-default-MadridCDN.tsv")
    mymap = [i.strip().split() for i in data2.readlines()]
    # TODO
    for myline in mymap:
        found = False
        for line_new in map_new:
            if myline[1] == line_new[1]:
                found = True
        if not found and is_number(myline[1]):
            myline[9] = "false"
            #map_new.append(myline)

    #pprint.pprint(map_new)
    #sys.exit()
    return map_new

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def output(map_new):

    data2 = open("C:\\PdV\\data\\map.tsv")
    map_orig = [i.strip().split() for i in data2.readlines()]
    
	# **********************************************
	# export file recolocation1
    recolocationmap = dict()
    for i in map_orig:
        if is_number(i[1]):
            myseat = i[0]
            recolocationmap[myseat] = i[1]
    #pprint.pprint(recolocationmap)
    #sys.exit()

    recolocation = []
    for m in map_new:
        try:
            recolocationmap[str(m[0])]
        except :
            pass
        else:
            if recolocationmap[str(m[0])] and is_number(m[1]):
                a = [recolocationmap[str(m[0])], m[0]]
                recolocation.append(a)
    #pprint.pprint(recolocation)
    print "Number of recolocations:"
    print len(recolocation)
    # WRITE FILE
    f1 = open('C:\\PdV\\data-tmp\\recolocation1.tsv', "w")
    f1.write("%s\n" % "seat old -> seat new")
    for entry in recolocation:
        f1.write("%s\n" % "\t".join([str(x) for x in entry]))
    f1.close()

if __name__ == '__main__':
    usage = """usage: %prog [-m mode] [options]"""
    version = "%prog " + __version__
    parser = OptionParser(usage=usage, version=version)
    parser.add_option("-m", "--mode", nargs=1, choices=["results", "speed", "simple1"],
        dest="mode", help="Either ('results', 'speed', 'simple1')")
    parser.add_option("-n", "--num-groups", default=3, type="int",
        dest="num_groups", help="How many groups to build (default=3)")
    parser.add_option("-r", "--reorder", default=False,
        action="store_true", dest="reorder", help="Use this flag to reorder")
    parser.add_option("-o", "--out-fn", nargs=1,
        dest="out_fn", help="Output filename for new map.tsv (optional)")
    parser.add_option("-c", "--count_abstention_as", nargs=1, default=None,
        dest="vote_id", help="Count abstention to a specific vote")
    #parser.add_option("-id", "--screen_id", nargs=1, default=715, type="int",
    #    dest="questionID", help="Add the screen ID (mandatory)")
    (options, args) = parser.parse_args()
    print options
    print
    #exit(0)

    #noinspection PyUnreachableCode,PyUnreachableCode,PyUnreachableCode,PyUnreachableCode,PyUnreachableCode,PyUnreachableCode,PyUnreachableCode
    if not options.mode:
        parser.error("Please specify a mode")

    elif options.mode == "results":
        map_new = analyze(mode=MODE_VOTE_RESULT, reorder=options.reorder,
                num_groups=options.num_groups, abstention_id=options.vote_id)
        # Block all the keypads except one, for every group.

        recolocation = output(map_new)
        #print recolocation


        # Write the new map to this tsv file
        f1 = open('C:\\PdV\\data-tmp\\recolocation2.tsv', "w")
        f1.write("%s\n" % "seat old -> seat new")
        for entry in recolocation:
            f1.write("%s\n" % "\t".join([str(x) for x in entry]))
        f1.close()

    elif options.mode == "speed":
        map_new = analyze(mode=MODE_VOTE_SPEED, reorder=options.reorder,
                num_groups=options.num_groups, abstention_id=options.vote_id)

    elif options.mode == "simple1":
        # Every keypad votes; we regroup simply based on the order of correlating-votes-sums
        map_new = analyze_simpleMar(abstention_id=options.vote_id)
        output(map_new)
        #print recolocation
        # Write the new map to this tsv file
        


    if options.out_fn:
        # Log the old map in data-tmp/log/
            # Check if the file exist
        fn = "C:\\PdV\\data\\map.tsv"
        shutil.copyfile(fn, "C:\\PdV\\data-tmp\\log\\map-%s-%s.tsv" % (715, int(time.time())))
        # Write the new map to thr map.tsv file
        f = open(options.out_fn, "w")
        f.write("seatid\tkeypadid\tXcolumn\tYrow\tXpx\tYpx\tsection\tgroup\ttype\tactive\tgender\n")
        myoutput = ""
        for entry in map_new:
            if "keypad" not in entry:
                #print "%s\n" % "\t".join([str(x) for x in entry])
                myoutput += "%s\n" % "\t".join([str(x) for x in entry])
        myoutput = myoutput.strip()
        f.write(myoutput)
        f.close()
        print "+++++++++++++++++++++++++++++++++++++"
        #print myoutput
        #print len(map_new)

