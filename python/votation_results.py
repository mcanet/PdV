"""This file gets the votation list (key.tsv) and then adds the votation results
    to the active(yes,no,abs|true,false,block) column in map.tsv for no ("false" or "block") keypadid.' '\n'
 'Finally it log map.tsv in data-temp/log/ and rewrites data-temp/map.tsv"""

import pprint
import time
import shutil
import sys
import os
import common

c = common

# Getting first argument

usage = """
	Usage:
		python votation_results.py [questionID] "gender"(optional)
		"""
#noinspection PyBroadException
try:
    sys.argv[1]
except:
    print usage
    sys.exit(1)
else:
    questionID = sys.argv[1]


#noinspection PyBroadException
try:
    sys.argv[2]
except:
    gender = ""
    pass
else:
    gender = sys.argv[2]

#### Getting the data
data1 = open(c.pdvdatatmp+"key.tsv")
votes = [i.strip().split() for i in data1.readlines()]

print ' -> number of votes: '+str(len(votes))

# add key.tsv to allkey.tsv. BUT change the first element of each newline (!)
f = open(c.pdvdatatmp+"allkey.tsv", 'a') # 'a' open existing file to append new line
timename = int(time.time())
for entry in votes:
    if entry[0] != "Topic":
        entry[0] = timename
    f.write("%s\n" % "\t".join([str(x) for x in entry]))
f.close()
print ' -> Appended votes from key.tsv to data-tmp/allkey.tsv'

data2 = open(c.pdvdata+"map.tsv")
map = [i.strip().split() for i in data2.readlines()]

#pprint.pprint (votes)

####################################
def main():
    
    if int(questionID) >= 205:
        abs = []  #check4abs()
    else:
        abs = []
     
    log_rewrite_map(questionID, votes2map(map, get_votations(votes), gender, abs, questionID))
    #debug()

def check4abs():
    """
    THIS DEF IS NOT ACTIVE ANYMORE!
    Check if a voter , has voted 4 abs for the last 4 votations. It true, then type=block them
    """
    # Get the list of log maps:
    pathlog = c.pdvdatatmplog
    maps = []
    for filename in os.listdir(pathlog):
        name = "map-"
        if name in filename:
            maps.append(filename)
    maps.reverse()
    maps = maps[:4]
    print  "--->"
    print maps
    abs = []
    c = 0
    for map in maps:
        data = open(pathlog+map)
        votes = [i.strip().split() for i in data.readlines()]
        c += 1
        # Check abstentions
        print "map checking: "+map
        for vote in votes:
            if vote[9] == "abs" and c<2:
                abs.append(vote[1])
            if vote[9] != "abs" and vote[1] in abs:
                try:
                    print "remove: "+str(vote[1])
                    abs.remove(vote[1])
                except:
                    pass
        print abs
    print abs
    print "---------------"
    return abs

def get_votations(votes):
    votes_list = dict()
    for vote in votes:
        if is_number(vote[4]):
            votes_list[vote[3]] = vote[4]
    return votes_list

def votes2map(map, votes_list, gender, abs, questionID):
    new_map = []
    maphead = ""
    count = dict()
    for line in map:
        if int(questionID) > 2000:
            if line[9] == "yes" or line[9] == "no" or line[9] == "abs" or line[9] == "true":
                count[line[1]] = line[9]
        if len(abs) > 0 and line[1] in abs:
            line[9] = "block"
        if is_number(line[0]):
            if line[9] != "false" and line[9] != "block":
                if line[1] in votes_list :
                    if votes_list[line[1]] == "1":
                        line[9] = "yes"
                        if gender == "gender":
                            line[10] = "m"
                    elif votes_list[line[1]] == "2":
                        line[9] = "no"
                        if gender == "gender":
                            line[10] = "w"
                    elif votes_list[line[1]] == "3":
                        line[9] = "abs"
                else:
                    #this are the voters who have not vote but could do it
                    if int(questionID) == 1:
                        line[9] = "false"
                    else:
                        line[9] = "abs"
            new_map.append(line)
        else:
            maphead = line
    new_map.insert(0, maphead)
    if gender == "gender":
        print  "   (Added m/w for Men/Women in column gender of map.tsv)"
    if int(questionID) > 2000:
        # Write the new map to this tsv file
        f = open(c.pdvdatatmp+"count5.tsv", "a")
        for entry in count:
            f.write("%s\t%s\n" % (entry, count[entry]))
            pprint.pprint("%s\t%s\n" % (entry, count[entry]))
        f.write("--\t--\n")
        f.close()
        print "Counter: "
        print count
    return new_map

def list2tsv(list):
    mytsv = ""
    for line in list:
        for l in line:
            mytsv += "%s\t" % l
        mytsv += "\n"
    mytsv = mytsv.strip()
    return mytsv

def log_rewrite_map(questionID, map_new):
    """
    Log the old map in data-tmp/log/
    Check if the file exist
    """
    fn = c.pdvdata+"map.tsv"
    shutil.copyfile(fn, c.pdvdatatmplog+"map-%s-%s.tsv" % (questionID, int(time.time())))
    print ' -> map.tsv log in '+c.pdvdatatmplog
    # Write the new map to this tsv file
    f = open(fn, "w")
    for entry in map_new:
        f.write("%s\n" % "\t".join([str(x) for x in entry]))
        #pprint.pprint("%s\n" % "\t".join([str(x) for x in entry]))
    f.close()
    print ' -> a new map.tsv writen'
    print

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def debug():
    data = c.pdvdata+"debug.txt"
    f = open(data, "w")
    f.write("votations call\n")
    f.close()


###################
main()