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

class MySplashScreen(SplashScreen):
    """
    Create a splash screen widget.
    """
    def __init__(self, parent=None):

        #------------

        # This is a recipe to a the screen.
        # Modify the following variables as necessary.
        bitmap = wx.Bitmap(name="Splash.png", type=wx.BITMAP_TYPE_PNG)
        splash = wx.adv.SPLASH_CENTRE_ON_SCREEN | wx.adv.SPLASH_TIMEOUT
        duration = 3000 # milliseconds

        # Call the constructor with the above arguments
        # in exactly the following order.
        super(MySplashScreen, self).__init__(bitmap=bitmap,
                                             splashStyle=splash,
                                             milliseconds=duration,
                                             parent=None,
                                             id=-1,
                                             pos=wx.DefaultPosition,
                                             size=wx.DefaultSize,
                                             style=wx.STAY_ON_TOP |
                                                   wx.BORDER_NONE)

        self.Bind(wx.EVT_CLOSE, self.OnExit)

    #-----------------------------------------------------------------------

    def OnExit(self, event):
        """
        ...
        """

        # The program will freeze without this line.
        event.Skip()  # Make sure the default handler runs too...
        self.Hide()
    
class HeeksExpertApp(SimApp):
    def __init__(self):
        SimApp.__init__(self)
        MySplash = MySplashScreen()
        MySplash.CenterOnScreen(wx.BOTH)
        MySplash.Show(True)
        
    def GetAppTitle(self):
        return 'Heeks Expert'
       
    def GetAppConfigName(self):
        return 'HeeksExpert'

    def AddExtraRibbonPages(self, ribbon):
        SimApp.AddExtraRibbonPages(self, ribbon)
        
        page = RB.RibbonPage(ribbon, wx.ID_ANY, 'Test', ribbon.Image('cone'))
        panel = RB.RibbonPanel(page, wx.ID_ANY, 'Test', ribbon.Image('cone'))
        toolbar = RB.RibbonButtonBar(panel)
        Ribbon.AddToolBarTool(toolbar, 'Test1', 'cone', 'Test Area Functions', self.TestAreaFunctions)
        Ribbon.AddToolBarTool(toolbar, 'Test2', 'cone', 'Test Area Functions 2', self.TestAreaFunctions2)
 
        page.Realize()
        
    def TestAreaFunctions(self, e):
        # make a sphere
        object = step.NewSphere()
        
        # make a shadow of the sphere
        geom.set_accuracy(0.01)
        stl = object.GetTris(0.01)
        mat = geom.Matrix()
        shadow = stl.Shadow(mat, False)
        s2 = geom.Area(shadow)
        
        # time testing 100 union operations
        start_time = time.time()
        
        mat.Translate(geom.Point3D(1,0,0))
        for i in range(0,100):
            s2.Transform(mat)
            shadow.Union(s2)
            
        time_taken = time.time() - start_time

        sketch = cad.NewSketchFromArea(shadow)
        cad.AddUndoably(sketch)
        
        wx.MessageBox('time take for 100 unions = %.2f seconds' % time_taken)

    def print_time(self, msg):
        new_time = time.time()
        print(msg + ' - %.2f seconds' % (new_time - self.prev_time))
        self.prev_time = new_time
                
    def TestAreaFunctions2(self, e):
        self.start_time = time.time()
        self.prev_time = self.start_time
        self.part_stl = geom.Stl('c:/tmp/shadow.stl')
        self.print_time('part loaded')
        machining_areas = self.part_stl.GetMachiningAreas()
        self.print_time('GetMachiningAreas()')

app = HeeksExpertApp()
app.MainLoop()

