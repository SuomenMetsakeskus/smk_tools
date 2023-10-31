# -*- coding: utf-8 -*-

"""
/***************************************************************************
 smk_tools
                                 A QGIS plugin
 Suomen metsäkeskuksen työkalut
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-10-04
        copyright            : (C) 2022 by Suomen metsäkeskus
        email                : mikko.kesala@metsakeskus.fi
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Suomen metsäkeskus'
__date__ = '2022-10-04'
__copyright__ = '(C) 2022 by Suomen metsäkeskus'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtGui import QIcon
import os,sys
from qgis.core import QgsProcessingProvider


pluginPath = os.path.dirname(__file__)
#sys.path.append(pluginPath)
#from .processing.focalstatistic_calculate import focal_toolsAlgorithm
from .processing.saastopuu_algorithm import saastopuu_toolsAlgorithm
from .processing.suojakaista_algorithm import suojakaista_toolsAlgorithm
from .processing.suojakaista_algorithm_wbt import suojakaista_toolsAlgorithm_wbt
from .processing.valumaalue_algorithm import Valumamalli
from .processing.saaastopuu_algorithm_qgisdata import saastopuu_toolsAlgorithm_qgis
from .processing.essmodels2points import essmodels2points


class smk_toolsProvider(QgsProcessingProvider):

    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)
    
    def icon(self):
        """
        add icon
        """
        iconPath = os.path.join(pluginPath, 'icon.jpg')

        return QIcon(os.path.join(iconPath))

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        self.addAlgorithm(suojakaista_toolsAlgorithm())
        self.addAlgorithm(suojakaista_toolsAlgorithm_wbt())
        self.addAlgorithm(saastopuu_toolsAlgorithm())
        self.addAlgorithm(saastopuu_toolsAlgorithm_qgis())
        self.addAlgorithm(Valumamalli())
        self.addAlgorithm(essmodels2points())
        #self.addAlgorithm(focal_toolsAlgorithm())
        
        

        # add additional algorithms here
        # self.addAlgorithm(MyOtherAlgorithm())

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'Suomen metsäkeskus'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr('Suomen metsäkeskus')
    
    """    def icon(self):
    
        Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        
        return QgsProcessingProvider.icon(self)
    """

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
