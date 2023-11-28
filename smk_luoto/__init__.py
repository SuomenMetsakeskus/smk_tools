# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SMK_Luoto
                                 A QGIS plugin
 Metsäkeskuksen Luoto-sovelluksen työkalut
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-11-28
        copyright            : (C) 2023 by Suomen metsäkeskus
        email                : luontotieto@metsakeskus.fi
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

__author__ = 'Suomen metsäkeskus'
__date__ = '2023-11-28'
__copyright__ = '(C) 2023 by Suomen metsäkeskus'


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load SMK_Luoto class from file SMK_Luoto.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .smk_luoto import SMK_LuotoPlugin
    return SMK_LuotoPlugin()
