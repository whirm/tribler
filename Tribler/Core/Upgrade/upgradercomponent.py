# upgradercomponent.py ---
#
# Filename: upgradercomponent.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Fri Mar  6 14:28:53 2015 (+0100)

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
import os

import wx
from twisted.internet.threads import deferToThread

from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.DownloadConfig import get_default_dest_dir, get_default_dscfg_filename
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.session_component import AbstractSessionComponent
from Tribler.Main.Utility.compat import convertDefaultDownloadConfig, convertMainConfig, convertSessionConfig
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.TriblerUpgradeDialog import TriblerUpgradeDialog
from Tribler.Main.vwxGUI.abcapp import ABCApp

# used by the anon tunnel tests as there's no way to mess with the Session before running the test ATM.
FORCE_ENABLE_TUNNEL_COMMUNITY = False
SKIP_TUNNEL_DIALOG = os.environ.get("TRIBLER_SKIP_OPTIN_DLG", "False") == "True"

logger = logging.getLogger(__name__)


class UpgraderComponent(AbstractSessionComponent):

    def __init__(self, session, autoload_discovery, *argv, **kwargs):
        super(UpgraderComponent, self).__init__(session, *argv, **kwargs)

        self.autoload_discovery = autoload_discovery
        self.app = None

    def start(self):
        self.startup_d = self.shutdown_d = deferToThread(self._wx_loop)
        return self.startup_d

    def stop(self):
        if not self.shutdown_d.called:
            self.startup_d.chainDeferred(self.shutdown_d)
        return self.shutdown_d

    def _wx_loop(self):
        # Launch first abc single instance
        if not self.app:
            self.app = wx.PySimpleApp(redirect=False)

        def do_upgrade():
            try:
                self._do_upgrade()
            except Exception, e:
                self.onStartupFailure(e)

        placeholder = wx.Frame(None)
        placeholder.Hide()

        wx.CallAfter(do_upgrade)
        self.app.MainLoop()

    def _do_upgrade(self):
        installdir = ABCApp.determine_install_dir()

        self.gui_image_manager = GuiImageManager.getInstance(installdir)

        # Start Tribler Session
        defaultConfig = SessionStartupConfig()
        state_dir = defaultConfig.get_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)

        self._logger.debug(u"Session config %s", cfgfilename)
        try:
            self.sconfig = SessionStartupConfig.load(cfgfilename)
        except:
            try:
                self.sconfig = convertSessionConfig(os.path.join(state_dir, 'sessconfig.pickle'), cfgfilename)
                convertMainConfig(state_dir, os.path.join(state_dir, 'abc.conf'),
                                  os.path.join(state_dir, 'tribler.conf'))
            except:
                self.sconfig = SessionStartupConfig()
                self.sconfig.set_state_dir(state_dir)

        self.sconfig.set_install_dir(installdir)

        # Arno, 2010-03-31: Hard upgrade to 50000 torrents collected
        self.sconfig.set_torrent_collecting_max_torrents(50000)

        dlcfgfilename = get_default_dscfg_filename(self.sconfig.get_state_dir())
        self._logger.debug("main: Download config %s", dlcfgfilename)
        try:
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        except:
            try:
                defaultDLConfig = convertDefaultDownloadConfig(
                    os.path.join(state_dir, 'dlconfig.pickle'), dlcfgfilename)
            except:
                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        if not defaultDLConfig.get_dest_dir():
            defaultDLConfig.set_dest_dir(get_default_dest_dir())
        if not os.path.isdir(defaultDLConfig.get_dest_dir()):
            try:
                os.makedirs(defaultDLConfig.get_dest_dir())
            except:
                # Could not create directory, ask user to select a different location
                dlg = wx.DirDialog(None,
                                   "Could not find download directory, please select a new location to store your downloads",
                                   style=wx.DEFAULT_DIALOG_STYLE)
                dlg.SetPath(get_default_dest_dir())
                if dlg.ShowModal() == wx.ID_OK:
                    new_dest_dir = dlg.GetPath()
                    defaultDLConfig.set_dest_dir(new_dest_dir)
                    defaultDLConfig.save(dlcfgfilename)
                    self.sconfig.save(cfgfilename)
                else:
                    # Quit
                    self.onError = lambda e: self._logger.error(
                        "tribler: quitting due to non-existing destination directory")
                    raise Exception()

        if FORCE_ENABLE_TUNNEL_COMMUNITY:
            self.sconfig.set_tunnel_community_enabled(True)

        if not self.sconfig.get_tunnel_community_optin_dialog_shown() and not SKIP_TUNNEL_DIALOG:
            optin_dialog = wx.MessageDialog(None,
                                            'If you are not familiar with proxy technology, please opt-out.\n\n'
                                            'This experimental anonymity feature using Tor-inspired onion routing '
                                            'and multi-layered encryption.'
                                            'You will become an exit node for other users downloads which could get you in '
                                            'trouble in various countries.\n'
                                            'This privacy enhancement will not protect you against spooks or '
                                            'government agencies.\n'
                                            'We are a torrent client and aim to protect you against lawyer-based '
                                            'attacks and censorship.\n'
                                            'With help from many volunteers we are continuously evolving and improving.'
                                            '\n\nIf you aren\'t sure, press Cancel to disable the \n'
                                            'experimental anonymity feature',
                                            'Do you want to use the experimental anonymity feature?',
                                            wx.ICON_WARNING | wx.OK | wx.CANCEL)
            enable_tunnel_community = optin_dialog.ShowModal() == wx.ID_OK
            self.sconfig.set_tunnel_community_enabled(enable_tunnel_community)
            self.sconfig.set_tunnel_community_optin_dialog_shown(True)
            optin_dialog.Destroy()
            del optin_dialog
        session = Session(self.sconfig)

        # check and upgrade
        upgrader = session.prestart()

        if not upgrader.is_done:
            upgrade_dialog = TriblerUpgradeDialog(self.gui_image_manager, upgrader)
            failed = upgrade_dialog.ShowModal()
            upgrade_dialog.Destroy()
            if failed:
                wx.MessageDialog(None, "Failed to upgrade the on disk data.\n\n"
                                 "Tribler has backed up the old data and will now start from scratch.\n\n"
                                 "Get in contact with the Tribler team if you want to help debugging this issue.\n\n"
                                 "Error was: %s" % upgrader.current_status,
                                 "Data format upgrade failed", wx.OK | wx.CENTRE | wx.ICON_EXCLAMATION).ShowModal()

        self.session = session
        self.gui_image_manager.delInstance()
        self.app.ExitMainLoop()


#
# upgradercomponent.py ends here
