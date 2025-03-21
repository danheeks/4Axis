import nc
import iso
import math
import datetime
import time
import os
import sys
up1 = os.path.abspath('..')
sys.path.insert(0, up1)
import area

now = datetime.datetime.now()

################################################################################
class Creator(iso.Creator):

    def __init__(self):
        iso.Creator.__init__(self)
        self.output_tool_definitions = False
        self.output_block_numbers = False
        self.top_z = None # z height for retract
        self.bottom_rapid_z = None # lowest rapid down to height
        self.bottom_feed_z = None # height to feed down to
        self.px = None # previous x,y coordinate
        self.py = None
        self.chamfer = None; # set to value, eg. 30, 45, 60 to output B and 45 degree moves
        self.moves = [] # make a list of moves and output at the end once we've found all the heights
        # move is sx, sy, ex, ey
        
    def SPACE_STR(self): return ' '

    def program_begin(self, id, comment):
        self.write('%\n')
        self.write( ('(Created with tangent_knife '))
        if self.chamfer:
            self.write('( chamfer )')
        self.write((' post processor ' + str(now.strftime("%Y/%m/%d %H:%M")) + ')' + '\n') )
        self.write('M3\n')
        
    def program_end(self):
        for px, py, x, y in self.moves:
            # start of a feed move
            
            # rapid to the top_z height
            iso.Creator.rapid(self, z = self.top_z)

            # calculate the tangent angle
            angle = math.atan2(y - py, x - px) * 57.295779513082320 # radians to degrees
            
            if self.chamfer != None and math.fabs(self.chamfer) < 89.0:
                forwards = area.Point(x-px, y - py) # vector along next line
                forwards.normalize() # make it a unit vector
                leftwards = ~forwards
                entry_depth = self.bottom_rapid_z - self.bottom_feed_z
                s = area.Point(px, py) + leftwards * (entry_depth * math.tan(self.chamfer * 0.017453292519943))
                
                # angle the cutter while rapiding to the start of the move
                iso.Creator.rapid(self, s.x, s.y, None, a = angle, b = self.chamfer)
            else:
                # angle the cutter while rapiding to the start of the move
                iso.Creator.rapid(self, px, py, None, a = angle)

            # rapid down
            iso.Creator.rapid(self, z = self.bottom_rapid_z)
            
            if self.chamfer:            
                # feed down
                iso.Creator.feed(self, px, py, z = self.bottom_feed_z)
            else:
                # feed down
                iso.Creator.feed(self, z = self.bottom_feed_z)

            # do the feed move
            iso.Creator.feed(self, x, y)

            if self.chamfer:            
                # rapid out at an angle
                e = area.Point(x, y) + leftwards * (entry_depth * math.tan(self.chamfer * 0.017453292519943))
                iso.Creator.rapid(self, e.x, e.y, z = self.bottom_rapid_z)
        
        # rapid to the top_z height
        iso.Creator.rapid(self, z = self.top_z)

        self.write('M5\n')
        self.write('G00 X0.0000 Y0.0000\n')
        self.write('M2\n')
        self.write('%')
        
        self.file_close()        
        
    def write_misc(self):
        # ignore M3
        pass
        
    def write_spindle(self):
        # ignore S3000
        pass
    
    def absolute(self):
        # ignore G90
        pass
    
    def tool_change(self, id):
        # ignore tool change
        pass
    
    def set_plane(self, plane):
        # ignore G17
        pass
    
    def rapid(self, x=None, y=None, z=None, a=None, b=None, c=None, newline = True ):
        if x != None:
            self.px = x
        if y != None:
            self.py = y
        
        if z != None:
            if self.top_z == None or z > self.top_z:
                self.top_z = z
            if self.bottom_rapid_z == None or z < self.bottom_rapid_z:
                self.bottom_rapid_z = z
        
        # don't do the rapid until we know the angle from the feed move
        #iso.Creator.rapid(x, y, None, None, None, None)
        
    def feed(self, x=None, y=None, z=None, a=None, b=None, c=None):
        if z != None:
            if self.bottom_feed_z == None or z < self.bottom_feed_z:
                self.bottom_feed_z = z
                
        if (x != None) or (y != None):
            if x == None:
                x = self.px
            if y == None:
                y = self.py

            if x != self.px or y != self.py:
                self.moves.append((self.px, self.py, x, y))
            self.px = x
            self.py = y
           
################################################################################

nc.creator = Creator()
