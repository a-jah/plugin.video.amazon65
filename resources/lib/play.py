#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import common
import random
import threading

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
urllib2 = common.urllib2
sys = common.sys
xbmcgui = common.xbmcgui
re = common.re
json = common.json
addon = common.addon
os = common.os
hashlib = common.hashlib
time = common.time
Dialog = xbmcgui.Dialog()

platform = 0
osWindows = 1
osLinux = 2
osOSX = 3
osAndroid = 4
if xbmc.getCondVisibility('system.platform.windows'):
    platform = osWindows
if xbmc.getCondVisibility('system.platform.linux'):
    platform = osLinux
if xbmc.getCondVisibility('system.platform.osx'):
    platform = osOSX
if xbmc.getCondVisibility('system.platform.android'):
    platform = osAndroid
if xbmc.getCondVisibility('System.Platform.Linux.RaspberryPi'):
    platform = 0

hasExtRC = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)') == True
useIntRC = addon.getSetting("remotectrl") == 'true'
browser = int(addon.getSetting("browser"))
verbLog = addon.getSetting('logging') == 'true'


def IStreamPlayback(url, asin, trailer):
    values = getFlashVars(url)
    if not values:
        return

    vMT = 'Feature'
    if trailer == '1':
        vMT = 'Trailer'

    title, plot, mpd = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT, opt='&titleDecorationScheme=primary-content'), retmpd=True)
    licURL = getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)
    common.Log(mpd)
    listitem = xbmcgui.ListItem(path=mpd)

    if trailer == '1':
        if title:
            listitem.setInfo('video', {'Title': title + ' (Trailer)'})
        if plot:
            listitem.setInfo('video', {'Plot': plot})
    listitem.setProperty('inputstream.mpd.license_type', 'com.widevine.alpha')
    listitem.setProperty('inputstream.mpd.license_key', licURL)
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem=listitem)


def PLAYVIDEO():
    amazonUrl = common.BASE_URL + "/dp/" + common.args.asin
    trailer = common.args.trailer
    xbmc.Player().stop()
    IStreamPlayback(amazonUrl, common.args.asin, trailer)


def check_output(*popenargs, **kwargs):
    p = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    out, err = p.communicate()
    retcode = p.poll()
    if retcode != 0:
        c = kwargs.get("args")
        if c is None:
            c = popenargs[0]
            e = subprocess.CalledProcessError(retcode, c)
            e.output = str(out) + str(err)
            common.Log(e, xbmc.LOGERROR)
    return out.strip()


def getCmdLine(videoUrl, amazonUrl):
    scr_path = addon.getSetting("scr_path")
    br_path = addon.getSetting("br_path").strip()
    scr_param = addon.getSetting("scr_param").strip()
    kiosk = addon.getSetting("kiosk") == 'true'
    appdata = addon.getSetting("ownappdata") == 'true'
    cust_br = addon.getSetting("cust_path") == 'true'
    os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'), 'open -a ']
    # path(0,win,lin,osx), kiosk, profile, args

    br_config = [[(None, ['Internet Explorer\\iexplore.exe'], '', ''), '-k ', '', ''],
                 [(None, ['Google\\Chrome\\Application\\chrome.exe'], ['google-chrome', 'google-chrome-stable', 'google-chrome-beta', 'chromium-browser'], '"/Applications/Google Chrome.app"'),
                  '--kiosk ', '--user-data-dir=', '--start-maximized --disable-translate --disable-new-tab-first-run --no-default-browser-check --no-first-run '],
                 [(None, ['Mozilla Firefox\\firefox.exe'], ['firefox'], 'firefox'), '', '-profile ', ''],
                 [(None, ['Safari\\Safari.exe'], '', 'safari'), '', '', '']]

    if not cust_br:
        br_path = ''

    if platform != osOSX and not cust_br:
        for path in os_paths[platform]:
            for file in br_config[browser][0][platform]:
                if os.path.exists(path + file):
                    br_path = path + file
                    break
                else:
                    common.Log('Browser %s not found' % (path + file), xbmc.LOGDEBUG)
            if br_path:
                break

    if not os.path.exists(br_path) and platform != osOSX:
        return ''

    br_args = br_config[browser][3]
    if kiosk:
        br_args += br_config[browser][1]
    if appdata and br_config[browser][2]:
        br_args += br_config[browser][2] + '"' + os.path.join(common.pldatapath, str(browser)) + '" '

    if platform == osOSX:
        if not cust_br:
            br_path = os_paths[osOSX] + br_config[browser][0][osOSX]
        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' %s"%s"' % (br_args, videoUrl)

    return br_path


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def getStreams(suc, data, retmpd=False):
    if not suc:
        return ''

    title = plot = False
    if data.has_key('catalogMetadata'):
        title = data['catalogMetadata']['catalog']['title']
        plot = data['catalogMetadata']['catalog']['synopsis']

    for cdn in data['audioVideoUrls']['avCdnUrlSets']:
        for urlset in cdn['avUrlInfoList']:
            if retmpd:
                return title, plot, urlset['url']
            data = common.getURL(urlset['url'])
            fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
            fr = round(eval(fps_string + '.0'), 3)
            return str(fr).replace('.0', '')
    return ''


def getPlaybackInfo(url):
    if addon.getSetting("framerate") == 'false':
        return ''
    Dialog.notification(xbmc.getLocalizedString(20186), '', xbmcgui.NOTIFICATION_INFO, 60000, False)
    values = getFlashVars(url)
    if not values:
        return ''
    fr = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True))
    Dialog.notification(xbmc.getLocalizedString(20186), '', xbmcgui.NOTIFICATION_INFO, 10, False)
    return fr


def getFlashVars(url):
    cookie = common.mechanizeLogin()
    showpage = common.getURL(url, useCookie=cookie)
    #common.WriteLog(showpage, 'flashvars', 'w')
    if not showpage:
        Dialog.notification(common.__plugin__, Error('CDP.InvalidRequest'), xbmcgui.NOTIFICATION_ERROR)
        return False
    values = {}
    search = {'sessionID': "ue_sid='(.*?)'",
              'marketplace': "ue_mid='(.*?)'",
              'customer': '"customerID":"(.*?)"'}
    if 'var config' in showpage:
        flashVars = re.compile('var config = (.*?);', re.DOTALL).findall(showpage)
        flashVars = json.loads(unicode(flashVars[0], errors='ignore'))
        values = flashVars['player']['fl_config']['initParams']
    else:
        for key, pattern in search.items():
            result = re.compile(pattern, re.DOTALL).findall(showpage)
            if result:
                values[key] = result[0]

    for key in values.keys():
        if not values.has_key(key):
            Dialog.notification(common.getString(30200), common.getString(30210), xbmcgui.NOTIFICATION_ERROR)
            return False

    values['deviceTypeID'] = 'AOAGZA014O5RE'
    values['asin'] = common.args.asin
    values['userAgent'] = common.UserAgent
    values['deviceID'] = common.gen_id()
    rand = 'onWebToken_' + str(random.randint(0, 484))
    pltoken = common.getURL(common.BASE_URL + "/gp/video/streaming/player-token.json?callback=" + rand, useCookie=cookie)
    try:
        values['token'] = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except:
        Dialog.notification(common.getString(30200), common.getString(30201), xbmcgui.NOTIFICATION_ERROR)
        return False
    return values


def getUrldata(mode, values, format='json', devicetypeid=False, version=1, firmware='1', opt='', extra=False, useCookie=False, retURL=False, vMT='Feature', dRes='AudioVideoUrls%2CCatalogMetadata'):
    if not devicetypeid:
        devicetypeid = values['deviceTypeID']
    url = common.ATV_URL + '/cdp/' + mode
    url += '?asin=' + values['asin']
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&customerID=' + values['customer']
    url += '&deviceID=' + values['deviceID']
    url += '&marketplaceID=' + values['marketplace']
    url += '&token=' + values['token']
    url += '&format=' + format
    url += '&version=' + str(version)
    url += opt
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Http&audioTrackId=all'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
    if retURL:
        return url
    data = common.getURL(url, common.ATV_URL.split('//')[1], useCookie=useCookie)
    if data:
        jsondata = json.loads(data)
        del data
        if jsondata.has_key('error'):
            return False, Error(jsondata['error'])
        return True, jsondata
    return False, 'HTTP Fehler'


def Error(data):
    code = data['errorCode']
    common.Log('%s (%s) ' % (data['message'], code), xbmc.LOGERROR)
    if 'CDP.InvalidRequest' in code:
        return common.getString(30204)
    elif 'CDP.Playback.NoAvailableStreams' in code:
        return common.getString(30205)
    elif 'CDP.Playback.NotOwned' in code:
        return common.getString(30206)
    elif 'CDP.Authorization.InvalidGeoIP' in code:
        return common.getString(30207)
    elif 'CDP.Playback.TemporarilyUnavailable' in code:
        return common.getString(30208)
    else:
        return '%s (%s) ' % (data['message'], code)


class window(xbmcgui.WindowDialog):

    def __init__(self):
        xbmcgui.WindowDialog.__init__(self)
        self._stopEvent = threading.Event()
        self._pbStart = time.time()

    def _wakeUpThreadProc(self, process):
        starttime = time.time()
        while not self._stopEvent.is_set():
            if time.time() > starttime + 60:
                starttime = time.time()
                xbmc.executebuiltin("playercontrol(wakeup)")
            if process:
                process.poll()
                if process.returncode != None:
                    self.close()
            self._stopEvent.wait(1)

    def wait(self, process):
        common.Log('Starting Thread')
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc, args=(process,))
        self._wakeUpThread.start()
        self.doModal()
        self._wakeUpThread.join()

    def close(self):
        common.Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        vidDur = int(xbmc.getInfoLabel('ListItem.Duration')) * 60
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        isLast = xbmc.getInfoLabel('Container().Position') == xbmc.getInfoLabel('Container().NumItems')
        pBTime = time.time() - self._pbStart

        if pBTime > vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")
            if not isLast:
                xbmc.executebuiltin("Action(Up)")

    def onAction(self, action):
        if not useIntRC:
            return

        ACTION_SELECT_ITEM = 7
        ACTION_PARENT_DIR = 9
        ACTION_PREVIOUS_MENU = 10
        ACTION_PAUSE = 12
        ACTION_STOP = 13
        ACTION_SHOW_INFO = 11
        ACTION_SHOW_GUI = 18
        ACTION_MOVE_LEFT = 1
        ACTION_MOVE_RIGHT = 2
        ACTION_MOVE_UP = 3
        ACTION_MOVE_DOWN = 4
        ACTION_PLAYER_PLAY = 79
        ACTION_VOLUME_UP = 88
        ACTION_VOLUME_DOWN = 89
        ACTION_MUTE = 91
        ACTION_NAV_BACK = 92
        ACTION_BUILT_IN_FUNCTION = 122
        KEY_BUTTON_BACK = 275
        ACTION_BACKSPACE = 110
        ACTION_MOUSE_MOVE = 107

        actionId = action.getId()
        common.Log('Action: Id:%s ButtonCode:%s' % (actionId, action.getButtonCode()))

        if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, KEY_BUTTON_BACK, ACTION_MOUSE_MOVE]:
            Input(keys='{EX}')
        elif action in [ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE]:
            Input(keys='{SPC}')
        elif action == ACTION_MOVE_LEFT:
            Input(keys='{LFT}')
        elif action == ACTION_MOVE_RIGHT:
            Input(keys='{RGT}')
        elif action == ACTION_MOVE_UP:
            Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            Input(keys='{DWN}')
        elif action == ACTION_SHOW_INFO:
            Input(9999, 0)
            xbmc.sleep(800)
            Input(9999, -1)
        # numkeys for pin input
        elif actionId > 57 and actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)
