# Define the task name
TASK = twiki-wg

# Set Flight environment to be SKA.  The other choice is TST.  Include the
# Makefile.FLIGHT make file that does most of the hard work
FLIGHT = SKA
include /proj/sot/ska/include/Makefile.FLIGHT

# Installed data.
DATA = task_schedule.cfg index_template.html ssawg_index.html mpcwg_index.html twg_index.html

# telem_archive uses a number of dedicated perl and IDL scripts
SHARE = make_wg_index.py

.PHONY: doc

install: $(TEST_DEPS)
	mkdir -p $(INSTALL_SHARE)
	mkdir -p $(INSTALL_DATA)
#
	rsync --times --cvs-exclude $(SHARE) $(INSTALL_SHARE)/
	rsync --times --cvs-exclude $(DATA) $(INSTALL_DATA)/
