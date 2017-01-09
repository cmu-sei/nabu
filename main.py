#  Copyright 2011-2015 by Carnegie Mellon University
#
#  NO WARRANTY
#
#  THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING INSTITUTE
#  MATERIAL IS FURNISHED ON AN "AS-IS" BASIS.  CARNEGIE MELLON
#  UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR
#  IMPLIED, AS TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY
#  OF FITNESS FOR PURPOSE OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS
#  OBTAINED FROM USE OF THE MATERIAL.  CARNEGIE MELLON UNIVERSITY
#  DOES NOT MAKE ANY WARRANTY OF ANY KIND WITH RESPECT TO FREEDOM
#  FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

__author__ = "sei-mappel"

import logging
import math
import os
import sys
import time
import traceback
from argparse import ArgumentParser
from multiprocessing import pool, Pool, cpu_count, Process, Lock, current_process

import matplotlib.pyplot as plt
from scipy.spatial.distance import canberra
from scipy.cluster.hierarchy import *

from storage import dbgw
from process.parsers import parse
from util.str_utils import get_hash


NUMFEATURES = 7
lock = Lock()


def plock(msg):
    with lock:
        sys.stdout.write("%s" % msg)
        sys.stdout.flush()


def parse_file_set(fpath):
    try:
        fin = open(fpath, "r")
    except (TypeError, IOError) as e:
        logging.error("%s\nCould not read input, exiting." % e)
        sys.stderr.write("Could not read required job input file\n")
        sys.exit(1)
    else:
        lines = fin.readlines()
        fin.close()
        return set([line.rstrip('\n') for line in lines if not line.startswith('#')])


def shutdown(pool_, job_db):
    logging.debug("Shutting down pool")
    pool_.close()
    pool_.join()
    logging.debug("Pool shut down. Closing job database")
    job_db.close()


def pscore(pdf_name, thresh, ftrs, gdb_path, unique_graphs):
    pid = current_process().pid
    graph_db = dbgw.PdfDb(gdb_path)
    if not graph_db.init(graph_db.table, graph_db.cols):
        logging.error("pscore %d could not initialize db. exiting." % pid)
        sys.exit(-1)

    for edge_md5 in unique_graphs:
        pdf_id, ftrs_b = graph_db.load_family_features(edge_md5)
        # logging.debug("\t%s: %s" % (pdf_id, ftrs_b))
        try:
            can_dist = canberra(ftrs, ftrs_b)
        except ValueError:
            logging.error("pscore canberra calc error. likely bad features for %s or %s" % (pdf_name, pdf_id))
        else:
            if not thresh or can_dist <= thresh:
                plock("%s,%s,%s,%f\n" % (pdf_name, edge_md5, pdf_id, can_dist))


def save_score(pnum):
    global FILES, SIMSCORES
    FILES[pnum].write('\n'.join(SIMSCORES[pnum]))


def calc_workload(num_jobs, num_procs):
    if num_jobs <= num_procs:
        return 1, num_jobs
    chunk_size = int(math.floor(float(num_jobs) / num_procs))
    return chunk_size, num_procs


def calc_similarities(pdf, pdf_db, num_procs, thresh):
    unique_graphs = [row[0] for row in pdf_db.get_unique('e_md5')]
    unique_num = len(unique_graphs)
    chunk_size, num_procs = calc_workload(unique_num, num_procs)
    offsets = [x for x in range(0, unique_num, chunk_size)]
    logging.debug("calc_sim: %d procs offsets[%d] unique_graphs[%d]" % (num_procs, len(offsets), unique_num))

    procs = [Process(target=pscore, args=(
        pdf.name, thresh, pdf.ftr_vec, pdf_db.dbpath, unique_graphs[offsets[proc]:offsets[proc] + chunk_size])) for
             proc in range(num_procs)]

    logging.debug("nabu.calc_simil. starting  children")

    plock("subject,family,candidate,score\n")
    for proc in procs:
        proc.start()

    logging.debug("nabu.calc_simil. waiting on children")
    for proc in procs:
        proc.join()


def score_pdfs(argv, job_db, pdf_db):
    todo = parse_file_set(argv.fin)

    parse_func = parse.get_parser(argv.parser)
    if not parse_func:
        logging.error("main.score_pdfs did not find valid parser: %s" % argv.parser)
        sys.exit(1)

    for pdf_id in todo:
        sys.stdout.write("Scoring: %s\n" % pdf_id)
        if not os.path.isfile(pdf_id):
            logging.warning("main.score_pdfs not a file: %s" % pdf_id)
            continue

        pdf = parse_func(pdf_id)
        logging.debug("%s: %s" % (pdf.name, pdf.ftr_vec))

        pdf_db.save(pdf)
        calc_similarities(pdf, pdf_db, argv.procs, argv.thresh)


def build_graphdb(argv, job_db, pdf_db):
    if not argv.update:
        done = job_db.get_completed(argv.job_id)
        argv.todo.difference_update(done)
        del done

    cnt = 0
    total_jobs = len(argv.todo)
    sys.stdout.write("Total jobs: %s\n" % total_jobs)
    if total_jobs <= 0:
        sys.stdout.write("No work to do. Exiting\n")
        sys.exit(0)

    logging.debug("Available processes: %s" % argv.procs)

    num_procs = min(total_jobs, argv.procs)
    p = Pool(num_procs, maxtasksperchild=argv.chunk)
    logging.debug("Pool size: %d with tasks per child %d" % (num_procs, argv.chunk))

    pfunc = parse.get_parser(argv.parser)
    if not pfunc:
        logging.error("main.build_graphdb could not find parser: %s" % argv.parser)
        sys.exit(1)

    try:
        for pdf in p.imap_unordered(pfunc, argv.todo):
            cnt += 1
            sys.stdout.write("%7d/%7d\r" % (cnt, total_jobs))
            logging.debug("%s: %s/%s" % (pdf.name, cnt, total_jobs))
            pdf_db.save(pdf)
            job_db.mark_complete(args.job_id, pdf.path)
    except KeyboardInterrupt:
        logging.warning("\nTerminating pool...\n")
        sys.stderr.write("\nTerminating pool...\n")
        p.terminate()
    except pool.MaybeEncodingError as e:
        logging.error("main.build_graphdb imap error: %s" % e)
        sys.stderr.write("\nError in processing pool (%s of %s completed):\n%s\n" % (cnt, total_jobs, e))
        p.terminate()
    except Exception as e:
        sys.stderr.write("\nUnhandled error building PDF DB: %s\n%s\n" % (traceback.format_exc(), repr(e)))
        p.terminate()
    finally:
        sys.stdout.write("\nCompleted: %7d/%7d\n" % (cnt, total_jobs))
        shutdown(p, job_db)


def draw_clusters(argv, graph_db):
    unique_graphs = [row[0] for row in graph_db.get_unique('e_md5')]
    unique_num = len(unique_graphs)

    logging.info('draw_clusters: Clustering %d graphs' % unique_num)
    x = []
    for edge_md5 in unique_graphs:
        pdf_id, ftrs_b = graph_db.load_family_features(edge_md5)
        if not ftrs_b:
            sys.stderr.write("PDF has empty feature set: %s" % pdf_id)
        else:
            x.append(ftrs_b)

    try:
        plock("Linkage...\n")
        z = linkage(x, 'single', metric='canberra')
        plock("Creating dendrogram...\n")
        dendrogram(z, color_threshold=2)
    except ValueError as e:
        sys.stderr.write("SciPy linkage ValueError: %s\n" % e)
        if not x:
            sys.stderr.write("No PDF feature sets found. Empty or incorrect graph database?\n")
    else:
        plock("Showtime\n")
        plt.show()


def main(args):
    if args.fin:
        args.job_id = get_hash(os.path.abspath(args.fin) + args.action)
        args.todo = parse_file_set(args.fin)

    job_db = dbgw.JobDb(os.path.join(args.dbdir, args.jobdb))
    pdf_db = dbgw.PdfDb(os.path.join(args.dbdir, args.graphdb))

    if not job_db.init(job_db.table, job_db.cols) \
            or not pdf_db.init(pdf_db.table, pdf_db.cols):
        logging.error("main.main could not initialize db. exiting.")
        sys.exit(1)

    start = time.clock()
    if args.action == "build":
        logging.info("main.main Building graph database")
        build_graphdb(args, job_db, pdf_db)
        logging.info("Build finished in ~ %.3f" % (time.clock() - start))
    elif args.action == "score":
        logging.info("main.main Scoring graphs")
        score_pdfs(args, job_db, pdf_db)
        logging.info("Scoring finished in ~ %.3f" % (time.clock() - start))
    elif args.action == "cluster":
        logging.info("main.main Clustering graphs")
        sys.stdout.write("This feature is under construction.\n")
        draw_clusters(args, pdf_db)
        logging.info("Clustering finished in ~ %.3f" % (time.clock() - start))


if __name__ == "__main__":
    argparser = ArgumentParser()

    argparser.add_argument('action',
                           help="build | score | cluster (under construction)")
    argparser.add_argument('fin',
                           help="line separated text file of samples to run")
    argparser.add_argument('-b', '--beginning',
                           action='store_true',
                           default=False,
                           help="Start from beginning. Don't resume job file based on completed")
    argparser.add_argument('-c', '--chunk',
                           type=int,
                           default=1,
                           help="Chunk size in jobs. Default is num_procs * 1")
    argparser.add_argument('-d', '--debug',
                           action='store_true',
                           default=False,
                           help="Spam the terminal with debug output")
    argparser.add_argument('-g', '--graphdb',
                           default='nabu-graphdb.sqlite',
                           help='Graph database filename. Default is nabu-graphdb.sqlite')
    argparser.add_argument('-j', '--jobdb',
                           default='nabu-jobs.sqlite',
                           help='Job database filename. Default is nabu-jobs.sqlite')
    argparser.add_argument('--xmldb',
                           default='nabu-xml.sqlite',
                           help='xml database filename. Default is nabu-xml.sqlite')
    argparser.add_argument('--dbdir',
                           default='db',
                           help="Database directory. Default is .../nabu/db/")
    argparser.add_argument('--logdir',
                           default='logs',
                           help="Logging directory. Default is .../nabu/logs/")
    argparser.add_argument('--parser',
                           default='pdfminer',
                           help="Type of pdf parser to use. Default is pdfminer")
    argparser.add_argument('-p', '--procs',
                           type=int,
                           default=cpu_count(),
                           help="Number of parallel processes. Default is 2/3 cpu core count")
    argparser.add_argument('-t', '--thresh',
                           type=int,
                           default=0,
                           help="Threshold which reports only graphs with similarities at or below this value.")
    argparser.add_argument('-u', '--update',
                           default=False,
                           action='store_true',
                           help="Ignore completed jobs")

    args = argparser.parse_args()

    del argparser

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("Debug mode")
        for key in [arg for arg in dir(args) if not arg.startswith('_')]:
            logging.debug("%s: %s" % (key, getattr(args, key)))
    else:
        logging.basicConfig(filename=os.path.join(args.logdir, "nabu-%s.log" % time.strftime("%c").replace(" ", "_")))

    main(args)
