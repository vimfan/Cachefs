#!/bin/sh

mkdir -p profiler_report

REPORT_FILE=profiler_report/report.txt

# without debug overhead 
cmdline=`echo $@ | sed s/--debug//g`
echo "------------------------------" >> $REPORT_FILE
echo "| ${cmdline}" >> $REPORT_FILE
echo "------------------------------" >> $REPORT_FILE
python2.7 -m cProfile ${cmdline} >> $REPORT_FILE
