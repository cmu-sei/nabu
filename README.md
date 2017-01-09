About
=====
Nabu is a tool (work in progress) for parsing, constructing, and comparing the structural graphs of a large collection
 of PDF documents. The comparisons are based on the work of [NetSimile](http://arxiv.org/abs/1209.2684).
 
This tool grew from PDFrankenstein, and now includes javascript in the pdf database. To view the JS after building 
your database:

`sqlite3 -cmd "select js from pdfs" db/nabu-graphdb.sqlite`

Dependencies
------------
* networkx
* scipy
* matplotlib
* psycopg2 (PostGres python module, also requires Postgres)

Usage
-----

The workflow with Nabu will typically be:

1. Build a graph database from a collection of PDFs
2. Score the graphs for similarity
3. Draw dendogram clusters (TODO)

#### Building the Database

Build the graph database by parsing the specified PDFs. PDFs are given with full paths in a line separated file.
`python main.py [options] build <file input>`

#### Scoring the Database

Requires a list of files to score. If the files are not present in the graph database then they will be added. Nabu will output (in CSV format): `subject, family, candidate, score`

`python main.py [options] score <file input>`

#### Drawing Clusters

Runs from the graph database. Uses scipy and matplotlib to draw the dendrogram of the set of PDFs based on the 
similarity score. Currently uses Canberra distance metric.

`python main.py [options] cluster`

#### Options

```
positional arguments:
    action                build | score | cluster (under construction)
    fin                   line separated text file of samples to run
  
optional arguments:
    -h, --help            show this help message and exit
    -b, --beginning       Start from beginning. Don't resume job file based on completed
    -c CHUNK, --chunk CHUNK
                        Chunk size in jobs. Default is num_procs * 1
    -d, --debug           Spam the terminal with debug output
    -g GRAPHDB, --graphdb GRAPHDB
                        Graph database filename. Default is nabu-
                        graphdb.sqlite
    -j JOBDB, --jobdb JOBDB
                        Job database filename. Default is nabu-jobs.sqlite
    --xmldb XMLDB         xml database filename. Default is nabu-xml.sqlite
    --dbdir DBDIR         Database directory. Default is .../nabu/db/
    --logdir LOGDIR       Logging directory. Default is .../nabu/logs/
    --parser PARSER       Type of pdf parser to use. Default is pdfminer
    -p PROCS, --procs PROCS
                        Number of parallel processes. Default is 2/3 cpu core
                        count
    -t THRESH, --thresh THRESH
                        Threshold which reports only graphs with similarities
                        at or below this value.
    -u, --update          Ignore completed jobs
```

References
----------
[NetSimile](http://arxiv.org/abs/1209.2684)