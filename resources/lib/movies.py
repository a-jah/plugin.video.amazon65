#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import appfeed

from sqlite3 import dbapi2 as sqlite

import xbmc
import xbmcgui
import os

MOV_TOTAL = common.addon.getSetting("MoviesTotal")
if MOV_TOTAL == '' or MOV_TOTAL == '0':
    MOV_TOTAL = '2400'
MOV_TOTAL = int(MOV_TOTAL)
tmdb_art = common.addon.getSetting("tmdb_art")


def createMoviedb():
    c = MovieDB.cursor()
    c.execute('drop table if exists movies')
    c.execute('drop table if exists categories')
    c.execute('''create table movies
                (asin UNIQUE,
                 HDasin UNIQUE,
                 movietitle TEXT,
                 trailer BOOLEAN,
                 poster TEXT,
                 plot TEXT,
                 director TEXT,
                 writer TEXT,
                 runtime TEXT,
                 year INTEGER,
                 premiered TEXT,
                 studio TEXT,
                 mpaa TEXT,
                 actors TEXT,
                 genres TEXT,
                 stars FLOAT,
                 votes TEXT,
                 fanart TEXT,
                 isprime BOOLEAN,
                 isHD BOOLEAN,
                 isAdult BOOLEAN,
                 popularity INTEGER,
                 recent INTEGER,
                 audio INTEGER,
                 PRIMARY KEY(movietitle,year,asin))''')
    MovieDB.commit()
    c.close()


def lookupMoviedb(value, rvalue='distinct *', name='asin', single=True, exact=False, table='movies'):
    common.waitforDB('movie')
    c = MovieDB.cursor()
    if not c.execute('SELECT count(*) FROM sqlite_master WHERE type="table" AND name=(?)', (table,)).fetchone()[0]:
        return ''
    sqlstring = 'select %s from %s where %s ' % (rvalue, table, name)
    retlen = len(rvalue.split(','))
    if not exact:
        value = '%' + value + '%'
        sqlstring += 'like (?)'
    else:
        sqlstring += '= (?)'
    if c.execute(sqlstring, (value,)).fetchall():
        result = c.execute(sqlstring, (value,)).fetchall()
        if single:
            if len(result[0]) > 1:
                return result[0]
            return result[0][0]
        else:
            return result
    if (retlen < 2) and (single):
        return None
    return (None,) * retlen


def deleteMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    movietitle = lookupMoviedb(asin, 'movietitle')
    num = 0
    if movietitle:
        c = MovieDB.cursor()
        num = c.execute('delete from movies where asin like (?)', ('%' + asin + '%',)).rowcount
        if num:
            MovieDB.commit()
    return num


def updateMoviedb(asin, col, value):
    c = MovieDB.cursor()
    asin = '%' + asin + '%'
    sqlquery = 'update movies set %s=? where asin like (?)' % col
    result = c.execute(sqlquery, (value, asin)).rowcount
    return result


def loadMoviedb(movie_filter=False, value=False, sortcol=False):
    common.waitforDB('movie')
    c = MovieDB.cursor()
    if movie_filter:
        value = '%' + value + '%'
        return c.execute('select distinct * from movies where %s like (?)' % movie_filter, (value,))
    elif sortcol:
        return c.execute('select distinct * from movies where %s is not null order by %s asc' % (sortcol, sortcol))
    else:
        return c.execute('select distinct * from movies')


def getMovieTypes(col):
    common.waitforDB('movie')
    c = MovieDB.cursor()
    items = c.execute('select distinct %s from movies' % col)
    types = common.getTypes(items, col)
    c.close()
    return types


def getMoviedbAsins(isPrime=1, returnlist=False):
    c = MovieDB.cursor()
    content = ''
    sqlstring = 'select asin from movies where isPrime = (%s)' % isPrime
    if returnlist:
        content = []
    for item in c.execute(sqlstring).fetchall():
        if returnlist:
            content.append([','.join(item), 0])
        else:
            content += ','.join(item)
    return content


def addMoviesdb(full_update=True):
    try:
        if common.args.url == 'u':
            full_update = False
    except Exception:
        pass
    dialog = xbmcgui.DialogProgress()
    if full_update:
        if common.updateRunning():
            return
        dialog.create(common.getString(30120))
        dialog.update(0, common.getString(30121))
        createMoviedb()
        MOVIE_ASINS = []
        full_update = True
    else:
        MOVIE_ASINS = getMoviedbAsins(returnlist=True)

    page = 1
    goAhead = 1
    endIndex = 0
    new_mov = 0
    tot_mov = 0
    MAX = 120

    while goAhead == 1:
        json = appfeed.getList('Movie', endIndex, NumberOfResults=MAX)['message']['body']
        titles = json['titles']
        if json['approximateSize'] == 0:
            MAX = MAX - 20
            if MAX < 1:
                MAX = 120
            continue
        endIndex = json['endIndex']
        if titles:
            for title in titles:
                if full_update and dialog.iscanceled():
                    goAhead = -1
                    break
                if 'titleId' in title:
                    asin = title['titleId']
                    if '_duplicate_' not in title['title']:
                        found, MOVIE_ASINS = common.compasin(MOVIE_ASINS, asin)
                        if not found:
                            new_mov += ASIN_ADD(title)
                        tot_mov += 1
                        updateMoviedb(asin, 'popularity', tot_mov)
        if endIndex == 0:
            goAhead = 0
        page += 1
        if full_update:
            dialog.update(int((tot_mov) * 100.0 / MOV_TOTAL), common.getString(30122) % page, common.getString(30123) % new_mov)
        if full_update and dialog.iscanceled():
            goAhead = -1
    if goAhead == 0:
        updateLibrary()
        common.addon.setSetting("MoviesTotal", str(tot_mov))
        common.Log('Movie Update: New %s Deleted %s Total %s' % (new_mov, deleteremoved(MOVIE_ASINS), tot_mov))
        if full_update:
            setNewest()
            dialog.close()
            updateFanart()
        xbmc.executebuiltin("XBMC.Container.Refresh")
        MovieDB.commit()


def updateLibrary(asinlist=False):
    asins = ''
    if not asinlist:
        asinlist = common.SCRAP_ASINS(common.movielib % common.lib)
        MOVIE_ASINS = getMoviedbAsins(0, True)
        for asin in asinlist:
            found, MOVIE_ASINS = common.compasin(MOVIE_ASINS, asin)
            if not found:
                asins += asin + ','
        deleteremoved(MOVIE_ASINS)
    else:
        asins = ','.join(asinlist)

    if not asins:
        return

    titles = appfeed.ASIN_LOOKUP(asins)['message']['body']['titles']
    for title in titles:
        ASIN_ADD(title)


def setNewest(compList=False):
    if not compList:
        compList = common.getCategories()
    catList = compList['movies']
    c = MovieDB.cursor()
    c.execute('drop table if exists categories')
    c.execute('''create table categories(
                 title TEXT,
                 asins TEXT);''')
    c.execute('update movies set recent=null')
    count = 1
    for id_ in catList:
        if id_ == 'PrimeMovieRecentlyAdded':
            for asin in catList[id_]:
                updateMoviedb(asin, 'recent', count)
                count += 1
        else:
            c.execute('insert or ignore into categories values (?,?)', [id_, catList[id_]])
    MovieDB.commit()


def updateFanart():
    if tmdb_art == '0':
        return
    asin = movie = year = None
    sqlstring = 'select asin, movietitle, year, fanart from movies where fanart is null'
    c = MovieDB.cursor()
    common.Log('Movie Update: Updating Fanart')
    if tmdb_art == '2':
        sqlstring += ' or fanart like "%images-amazon.com%"'
    for asin, movie, year, oldfanart in c.execute(sqlstring):
        movie = movie.lower().replace('[ov]', '').replace('omu', '').replace('[ultra hd]', '').split('(')[0].strip()
        result = appfeed.getTMDBImages(movie, year=year)
        if oldfanart:
            if result == common.na or not result:
                result = oldfanart
        updateMoviedb(asin, 'fanart', result)
    MovieDB.commit()
    common.Log('Movie Update: Updating Fanart Finished')


def deleteremoved(asins):
    delMovies = 0
    for item in asins:
        if item[1] == 0:
            for asin in item[0].split(','):
                delMovies += deleteMoviedb(asin)
    return delMovies


def ASIN_ADD(title):
    isAdult = False
    stars = None
    votes = None
    poster = None
    runtime = None
    premiered = None
    year = None
    mpaa = ''
    genres = ''
    asin, isHD, isPrime, audio = common.GET_ASINS(title)
    movietitle = title['title']
    plot = title.get('synopsis')
    fanart = title.get('heroUrl')
    director = title.get('director')
    if 'runtime' in title:
        runtime = str(title['runtime']['valueMillis'] / 60000)
    if 'releaseOrFirstAiringDate' in title:
        premiered = title['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
        year = int(premiered.split('-')[0])
    studio = title.get('studioOrNetwork')
    if 'regulatoryRating' in title:
        if title['regulatoryRating'] == 'not_checked':
            mpaa = common.getString(30171)
        else:
            mpaa = common.getString(30170) + title['regulatoryRating']
    actors = title.get('starringCast')
    if 'genres' in title:
        genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
    trailer = title.get('trailerAvailable')
    if 'customerReviewCollection' in title:
        stars = float(title['customerReviewCollection']['customerReviewSummary']['averageOverallRating']) * 2
        votes = str(title['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
    elif 'amazonRating' in title:
        if 'rating' in title['amazonRating']:
            stars = float(title['amazonRating']['rating']) * 2
        if 'count' in title['amazonRating']:
            votes = str(title['amazonRating']['count'])
    if 'restrictions' in title:
        for rest in title['restrictions']:
            if rest['action'] == 'playback' and rest['type'] == 'ageVerificationRequired':
                isAdult = True
                break
    if 'images' in title['formats'][0]:
        thumbnailUrl = title['formats'][0]['images'][0]['uri']
        thumbnailFilename = thumbnailUrl.split('/')[-1]
        thumbnailBase = thumbnailUrl.replace(thumbnailFilename, '')
        poster = thumbnailBase + thumbnailFilename.split('.')[0] + '.jpg'
    titelnum = 0
    if 'bbl test' not in movietitle.lower() and 'test movie' not in movietitle.lower():
        moviedata = [common.cleanData(x) for x in [asin, None, common.checkCase(movietitle), trailer, poster, plot, director, None, runtime, year, premiered, studio, mpaa, actors, genres, stars, votes, fanart, isPrime, isHD, isAdult, None, None, audio]]
        c = MovieDB.cursor()
        num = c.execute('insert or ignore into movies values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', moviedata).rowcount
        if num:
            MovieDB.commit()
        titelnum += num
    return titelnum

if not os.path.exists(common.MovieDBfile):
    MovieDB = sqlite.connect(common.MovieDBfile)
    MovieDB.text_factory = str
    createMoviedb()
else:
    MovieDB = sqlite.connect(common.MovieDBfile)
    MovieDB.text_factory = str
