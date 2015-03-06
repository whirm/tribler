# session_component.py ---
#
# Filename: session_component.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Fri Mar  6 14:33:21 2015 (+0100)

# Commentary:
#
#
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:
import logging
from abc import ABCMeta, abstractmethod

from twisted.internet.defer import Deferred

from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractSessionComponent(TaskManager):
    """
    Abstract class that defines an asynchronous Session component.
    """
    __metaclass__ = ABCMeta

    def __init__(self, session):
        super(AbstractSessionComponent, self).__init__()

        self.session = session

        self._logger = logging.getLogger(self.__class__.__name__)

        self.startup_d = Deferred()
        self.shutdown_d = Deferred()
        self.shutdown_d.addBoth(self._pending_tasks_cleanup)

    def _pending_tasks_cleanup(self, result):
        self.cancel_all_pending_tasks()
        return result

    @abstractmethod
    def start(self):
        """
        Activates the component

        Returns:
            Deferred that will succeed/fail when the component startup sequence
            is completed.
        """

    @abstractmethod
    def stop(self):
        """
        Deactivates the component

        Returns:
            Deferred that will succeed/fail when the component shutdown sequence
            is completed.
        """

    @blocking_call_on_reactor_thread
    def onStartupFailure(self, failure):
        self.startup_d.errback(failure)

    @blocking_call_on_reactor_thread
    def onStarted(self, result=None):
        """
        Called when the startup sequence has finished.

        Args:

            result: (None or Failure): Optional Failure describing why the
            component startup failed.

        """
        self.startup_d.callback(result)

    @blocking_call_on_reactor_thread
    def onStopped(self, result=None):
        """
        Called when the shutdown sequence has finished.

        Args:

            result: (None or Failure): Optional Failure describing why the
            component shutdown failed.

        """
        self.shutdown_d.callback(result)

#
# session_component.py ends here
