import os
import sys

this_dir = os.path.dirname(os.path.realpath(__file__))
sim_dir = os.path.realpath(this_dir + '/../dsim')
sys.path.append(sim_dir)

import wx
from   wx.adv import SplashScreen as SplashScreen
from SimApp import SimApp
from Ribbon import RB
from Ribbon import Ribbon
import step
import geom
import cad
import time
import math
    
class HeeksExpertApp(SimApp):
    def __init__(self):
        SimApp.__init__(self)
        
    def GetAppTitle(self):
        return 'Heeks 4 Axis'
       
    def GetAppConfigName(self):
        return 'Heeks4Axis'

    def AddExtraOtherOperations(self, toolbar):
        save_bitmap_path = self.bitmap_path
        self.bitmap_path = this_dir + '/bitmaps'
        Ribbon.AddToolBarTool(toolbar, 'Unwrap Solid', 'unwrap', 'Unwrap Solid', self.MakeUnwrappedSolid)
        Ribbon.AddToolBarTool(toolbar, 'Split Test', 'split', 'Split to Smaller Triangles', self.SplitTest)
        self.bitmap_path = save_bitmap_path
        
    def MakeUnwrappedSolid(self, e):
        solids = []
        for object in cad.GetSelectedObjects():
            if object.GetIDGroupType() == cad.OBJECT_TYPE_STL_SOLID:
                solids.append(object)
                
        if len(solids) == 0:
            cad.ClearSelection(True)
            filter = cad.Filter()
            filter.AddType(cad.OBJECT_TYPE_STL_SOLID)
            if wx.GetApp().IsSolidApp():
                import step
                filter.AddType(step.GetSolidType())
            wx.GetApp().PickObjects('Pick solids to unwrap', filter, False)
        
            for object in cad.GetSelectedObjects():
                if object.GetIDGroupType() == cad.OBJECT_TYPE_STL_SOLID:
                    solids.append(object)
                    
        if len(solids) > 0:
            cad.StartHistory('Unwrap Solids')
            
            for object in solids:
                stl = object.GetTris(0.01)
                smaller_tris_stl = stl.SplitToSmallerTriangles(0.5)
                unwrapped_stl = smaller_tris_stl.Unwrap(10.0)
                new_object = cad.NewStlSolidFromStl(unwrapped_stl)
                cad.AddUndoably(new_object)
                
            cad.EndHistory()
            
    def SplitTest(self, e):
        solids = []
        for object in cad.GetSelectedObjects():
            if object.GetIDGroupType() == cad.OBJECT_TYPE_STL_SOLID:
                solids.append(object)
                
        if len(solids) == 0:
            cad.ClearSelection(True)
            filter = cad.Filter()
            filter.AddType(cad.OBJECT_TYPE_STL_SOLID)
            if wx.GetApp().IsSolidApp():
                import step
                filter.AddType(step.GetSolidType())
            wx.GetApp().PickObjects('Pick solids to split', filter, False)
        
            for object in cad.GetSelectedObjects():
                if object.GetIDGroupType() == cad.OBJECT_TYPE_STL_SOLID:
                    solids.append(object)
                    
        if len(solids) > 0:
            cad.StartHistory('Split Solids')
            
            for object in solids:
                stl = object.GetTris(0.01)
                smaller_tris_stl = stl.SplitToSmallerTriangles(0.5)
                new_object = cad.NewStlSolidFromStl(smaller_tris_stl)
                cad.AddUndoably(new_object)
                
            cad.EndHistory()
            
app = HeeksExpertApp()
app.MainLoop()

