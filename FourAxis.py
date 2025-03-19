# Copyright Dan Heeks September 2020
# This file is proprietary software and can be licensed from website url
# where latest updates can be downloaded
# Please do not share this file with anyone

import AutoProgramDlg
from HeeksConfig import HeeksConfig
import wx
import cad
import geom
import math
import step
import Program
import NcCode
import Stock
import Profile
import Pocket
import Drilling
import ScriptOp
import Tag
import Tags
import Tool
import time
from consts import *

MOVE_START_NOT = 0
MOVE_START_TO_MIDDLE_LEFT = 1

BOTTOM_NORMAL = 0
BOTTOM_THROUGH = 1
BOTTOM_POCKET = 2

MATERIAL_NAME_ACETAL = 'Acetal'
MATERIAL_NAME_POLYPROPYLENE = 'PolyPropylene'
MATERIAL_NAME_ALU_ALLOY = 'Alu Alloy'
MATERIAL_NAME_MILD_STEEL = 'Mild Steel'

slot_cutter_positions = [3,4,5,6]
drill_positions = [1,2,7,8,9]

FINISH_COLOR = cad.Color(128, 0, 255)

BIG_CUTTER_DIAMETER = 6.0 # maximum cutter diameter allowed when big_rigid_part is not ticked, otherwise allow any size tool

class AutoProgram:
    def __init__(self):
        self.ReadFromConfig()
        self.next_slot_cutter = 0
        self.next_drill = 0
        self.tools_to_add_at_end = {} # dictionary of tool id and Tool
        self.slot_cutters = AvailableTools(self, 'slot cutters', slot_cutter_positions)
        self.drills = AvailableTools(self, 'drills', drill_positions)
        self.part = None
        self.failure = None
        self.warnings = []
        self.stock_thicknesses = {
                 MATERIAL_NAME_ACETAL:[5.0, 6.0, 10.0, 20.0, 30.0, 40.0],
                 MATERIAL_NAME_POLYPROPYLENE:[5.0, 6.0, 9.0, 10.0, 20.0, 30.0, 40.0],
                 MATERIAL_NAME_ALU_ALLOY:[2.0, 3.0, 4.0, 5.0, 6.0, 10.0, 16.0, 20.0, 30.0, 40.0],
                 MATERIAL_NAME_MILD_STEEL:[2.0, 3.0, 4.0, 5.0, 6.0],
                 }
        self.precision_faces = []
        self.want_progress_dlg = False
        self.want_time_print = True

    def GetSlotCutters(self):
        return self.slot_cutters[self.material]
    
    def ReadFromConfig(self):
        config = HeeksConfig()
        self.x_margin = config.ReadFloat('XMargin', 20.0)
        self.y_margin = config.ReadFloat('YMargin', 3.0)
        self.material = config.Read('Material', MATERIAL_NAME_ALU_ALLOY)
        self.create_gcode = config.ReadBool('CreateGCode', True)
        self.tag_width = config.ReadFloat('TagWidth', 5.0)
        self.tag_height = config.ReadFloat('TagHeight', 1.0)
        self.tag_angle = config.ReadFloat('TagAngle', 45.0)
        self.tag_y_margin = config.ReadFloat('TagYMargin', 4.0)
        self.big_rigid_part = config.ReadBool('BigRigidPart', False) # tick this to use the big cutter
        self.precision = config.ReadFloat('Precision', 0.1)
        self.make_area_operations = config.ReadBool('MakeAreaOps', True)
        self.geometry_visible = config.ReadBool('GeomVisible', False)
        self.use_part_thickness = config.ReadBool('UsePartThickness', False)        
        
        
    def WriteToConfig(self):
        config = HeeksConfig()
        config.WriteFloat('XMargin', self.x_margin)
        config.WriteFloat('YMargin', self.y_margin)
        config.Write('Material', self.material)
        config.WriteBool('CreateGCode', self.create_gcode)
        config.WriteFloat('TagWidth', self.tag_width)
        config.WriteFloat('TagHeight', self.tag_height)
        config.WriteFloat('TagAngle', self.tag_angle)
        config.WriteFloat('TagYMargin', self.tag_y_margin)
        config.WriteBool('BigRigidPart', self.big_rigid_part)
        config.WriteFloat('Precision', self.precision)
        config.WriteBool('MakeAreaOps', self.make_area_operations)
        config.WriteBool('GeomVisible', self.geometry_visible)
        config.WriteBool('UsePartThickness', self.use_part_thickness)
    
    def Edit(self):
        res = AutoProgramDlg.Do(self)
        return res
    
    def progress_start(self):
        if self.want_time_print:
            self.start_time = time.time()
            self.last_time = self.start_time
            self.progress_text = 'Start'

        # show a progress dialog
        if self.want_progress_dlg:
            self.progress_percentage = 0
            self.progress_dlg = wx.ProgressDialog('Auto Program', 'Creating operations automatically...', parent = wx.GetApp().frame, style = wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)
    
    def progress_update(self, percentage_extra, txt):
        if self.want_time_print:
            new_time = time.time()
            print(self.progress_text + ' time = %0.2f' % (new_time - self.last_time))
            self.progress_text = txt
            self.last_time = new_time
        if self.want_progress_dlg:
            self.progress_percentage += percentage_extra
            self.progress_dlg.Update(self.progress_percentage, txt)
            
    def progress_end(self):
        if self.want_time_print:
            print('total_time = %0.2f' % (time.time() - self.start_time))
            
        if self.want_progress_dlg: self.progress_dlg.Destroy()
    
    def Run(self):
        cad.StartHistory('Create Operations')
        
        # test, just display machining areas as sketches
        if False:
            self.GetPart()
            self.part_stl = self.part.GetTris(self.precision)
            machining_areas = self.part_stl.GetMachiningAreas()
            
            cad.StartHistory()
            for ma in machining_areas:
                cad.AddUndoably(cad.NewSketchFromArea(ma.area))
            cad.EndHistory()
            
            return
        
        self.progress_start()

        try:
            # get the cutters for the material
            self.progress_update(1, 'Get Cutters...')
            self.slot_cutters.ImportToolsForMaterial(self.material.lower())
            
            # get the drills for the material
            self.progress_update(1, 'Get Drills...')
            self.drills.ImportToolsForMaterial(self.material.lower())
            
            # automatically create stocks, tools, operations, g-code
            self.progress_update(3, 'Get Part...')
            self.GetPart()
            
            # clear existing program
            self.ClearProgram()
            
            # add a cube and stock referencing it
            self.AddStock()
            
            # move the part, so stock is at origin
            self.progress_update(5, 'Move Part...')
            self.MovePart()
            
            self.progress_update(5, 'Make Shadow...')
            self.MakeShadow()
            self.stored_ops = []

            do_finish_operations = True
            
            if self.make_area_operations:
                self.progress_update(5, 'Make Area Operations...')
                self.MakePatchOperations(do_finish_operations)
                
            self.progress_update(5, 'Cut Shadow Inners...')
            self.CutShadowInners(do_finish_operations)
            for op in self.stored_ops:
                cad.AddUndoably(op, wx.GetApp().program.operations)
            self.stored_ops = []
            self.progress_update(5, 'Cut Outside...')
            self.CutOutside(do_finish_operations)
            
            self.progress_update(5, 'Add Tools At End...')
            self.AddToolsAtEnd()
            
            if self.failure:
                wx.MessageBox(self.failure, "ERROR!")
            else:
                if len(self.warnings) > 0:
                    s = ''
                    for warning in self.warnings:
                        if s:
                            s.append('\n')
                        s.append(warning)
                    wx.MessageBox(s, 'warnings only:')
        
                if self.create_gcode:
                    self.progress_update(5, 'Make G Code...')
                    wx.GetApp().program.MakeGCode()
                    self.progress_update(5, 'Read G Code for Toolpath View...')
                    wx.GetApp().program.BackPlot()
                    
            self.progress_end()

        except Exception as e:
            self.progress_end()
            import traceback
            print(traceback.format_exc())
            wx.MessageBox('error during Auto Program: ' + str(e))
            
        cad.EndHistory()
            
        wx.GetApp().frame.graphics_canvas.viewport.OnMagExtents(True, 6)
        wx.GetApp().frame.graphics_canvas.Refresh()
        
    def AddToolsAtEnd(self):
        if self.failure: return
        for tool_id in self.tools_to_add_at_end:
            cad.AddUndoably(self.tools_to_add_at_end[tool_id], wx.GetApp().program.tools)
            
    def CutShadowInners(self, do_finish_pass = True):
        # shadow inners are all the holes which go all the way through the part
        if self.failure: return
        curves_to_profile = []
        holes_to_profile = []
        holes_to_drill = []
        
        shadow_curves = self.shadow.GetCurves()
        for curve in shadow_curves:
            if curve.IsClockwise():
                circle = curve.IsACircle(self.precision)
                if circle == None:
                    curves_to_profile.append(curve)
                else:
                    hole = Hole(circle, 0.0, -self.thickness)
                    # add to existing holes
                    for h in holes_to_drill:
                        if h.AddHole(hole, self.precision):
                            hole = None
                            break
                    if hole != None:
                        holes_to_drill.append(hole)
                        
        for hole in holes_to_drill:
            hole.SortPoints()
            cut_depth = hole.top_z - hole.bottom_z
            tool_index = self.drills.GetToolOfDiameter(hole.diameter, cut_depth, self.precision)
            if tool_index == None:
                # no drill of this size
                holes_to_profile.append(hole)
                continue
            tool_id, default_tool = self.drills.AddIfNotAdded(tool_index)
            drilling = Drilling.Drilling()
            drilling.tool_number = tool_id
            for p in hole.pts:
                new_point = cad.NewPoint(geom.Point3D(p.x, p.y, 0.0))
                new_point.SetVisible(self.geometry_visible)
                cad.AddUndoably(new_point)
                drilling.points.append(new_point.GetID())
            drilling.start_depth = hole.top_z
            drilling.final_depth = hole.bottom_z
            drilling.horizontal_feed_rate = default_tool.hfeed
            drilling.vertical_feed_rate = default_tool.vfeed
            drilling.spindle_speed = default_tool.spin
            drilling.step_down = default_tool.rough_step_down
            cad.PyIncref(drilling)
            cad.AddUndoably(drilling, wx.GetApp().program.operations)
            
        for hole in holes_to_profile:
            self.ProfileHole(hole, do_finish_pass = do_finish_pass)
                        
        for curve in curves_to_profile:
            self.ProfileCurve(curve, do_finish_pass = do_finish_pass, inside = True, name = 'Shadow Inner')            

    def MakePatchOperations(self, do_finish_pass = True):
        if self.failure: return
        
        self.progress_update(1, 'Stl.GetMachiningAreas()')
        machining_areas = self.part_stl.GetMachiningAreas()
        
        debug_Union_count = 0
        
        self.progress_update(1, 'join areas of the same top level')
        # join areas of the same top level
        combined_machining_areas = []
        current_ma = None
        for ma in machining_areas:
            if current_ma == None or math.fabs(ma.top - current_ma.top) > self.precision:
                current_ma = ma
                combined_machining_areas.append(current_ma)
            else:
                debug_Union_count += 1
                current_ma.area.Union(ma.area)
                
        self.progress_update(1, 'RestMachine')
        
        level = 1 # for naming the operations
        
        for ma in combined_machining_areas:
#            sketch = cad.NewSketchFromArea(ma.area)
#            mat = geom.Matrix()
#            mat.Translate(geom.Point3D(0,0,ma.top))
#            sketch.Transform(mat)
#            cad.AddUndoably(sketch)
#            continue

            # ignore any area that is underneath an area already atexit_done
            ma.area.Subtract(self.area_done)

            if ma.top < -0.001:
                # pocket area
                
                # get a list of cutters ordered by biggest diameter first
                cut_depth = math.fabs(ma.top)
                patch_cutters = self.GetSortedCutters(cut_depth, rest_machining = True)
                
                self.RestMachine(ma.area, patch_cutters, 0.0, ma.top, bottom_style=BOTTOM_POCKET, do_finish_pass = do_finish_pass, store_ops = True, name = 'Level %i' % level)
                
                level += 1
            
            self.area_done.Union(ma.area)
        
    def MakeShadow(self):
        if self.failure: return
        self.part_stl = self.part.GetTris(self.precision)
        self.part_box = self.part_stl.GetBox()
        self.clearance_height = self.part_box.MaxZ() + 5.0
        mat = geom.Matrix()
        geom.set_fitarcs(False) # make sure FitArcs only happens when making the g-code
        self.part_stl.WriteStl('c:/tmp/shadow.stl')
        self.shadow = self.part_stl.Shadow(mat, False)
        sketch = cad.NewSketchFromArea(self.shadow)
        sketch.SetVisible(self.geometry_visible)
        cad.AddUndoably(sketch)
        self.shadow.Reorder()
        self.stock_area = self.MakeStockArea(self.shadow, self.x_margin, self.y_margin, self.x_margin, self.y_margin)
        self.area_done = geom.Area() # area_done starts empty, then is the area at the top ( top face ), then gets added to by each descending area until it should end up the same as the shadow of the part
        self.solid_area = None
        self.current_top_height = None
        
    def CutOutside(self, do_finish_pass = False):
        if self.failure: return
        for curve in self.shadow.GetCurves():
            if not curve.IsClockwise():
                self.ProfileCurve(curve, move_start_type = MOVE_START_TO_MIDDLE_LEFT, do_finish_pass = do_finish_pass, add_tags = True, name = 'Outside')         
                
    def ProfileHole(self, hole, do_finish_pass = False):
        radius = hole.diameter * 0.5
        for p in hole.pts:
            curve = geom.Curve()
            curve.Append(geom.Point(p.x - radius, p.y))
            curve.Append(geom.Vertex(-1, geom.Point(p.x + radius, p.y), geom.Point(p.x, p.y)))
            curve.Append(geom.Vertex(-1, geom.Point(p.x - radius, p.y), geom.Point(p.x, p.y)))
            self.ProfileCurve(curve, z_top = hole.top_z, z_bottom = hole.bottom_z, do_finish_pass = do_finish_pass, inside = True, name = 'Hole')
        
    def ProfileCurveWithCutter(self, curve, cutter_index, z_top = 0.0, z_bottom = None, move_start_type = MOVE_START_NOT, bottom_style = BOTTOM_THROUGH, material_allowance = 0.0, rough = True, add_tags = False, side = Profile.PROFILE_LEFT_OR_OUTSIDE, store_ops = False, name = None):
        tool_id, default_tool = self.slot_cutters.AddIfNotAdded(cutter_index)
        if self.failure:
            return

        #check that cutter can get unto the curve
        radius = default_tool.diam * 0.5
        if (side == Profile.PROFILE_RIGHT_OR_INSIDE) and curve.IsClosed():
            offset_area = geom.Area()
            c = geom.Curve(curve)
            if c.IsClockwise():
                c.Reverse()
            offset_area.Append(c)
            offset_area.Offset(radius + 0.1)
            if offset_area.NumCurves() == 0:
                return
        
        # create a sketch for the curve
        sketch = cad.NewSketchFromCurve(curve)
        sketch.SetVisible(self.geometry_visible)
        cad.AddUndoably(sketch)
        
        profile = Profile.Profile(sketch.GetID())
        profile.tool_number = tool_id
        profile.start_depth = z_top
        profile.pattern = 0
        profile.surface = 0
        if z_bottom == None:
            profile.final_depth = -self.thickness
        else:
            profile.final_depth = z_bottom
            
        profile.tool_on_side = side

        if move_start_type == MOVE_START_TO_MIDDLE_LEFT:
            profile.start_given = True
            box = curve.GetBox()
            profile.start = geom.Point3D(box.MinX(), (box.MinY() + box.MaxY())*0.5, 0.0)
            
        self.SetDepthOpBottomFromStyle(profile, bottom_style)

        # set operation from chosen tool info
        profile.horizontal_feed_rate = default_tool.hfeed
        profile.vertical_feed_rate = default_tool.vfeed
        profile.spindle_speed = default_tool.spin
        profile.step_down = default_tool.rough_step_down if rough else default_tool.finish_step_down
        profile.auto_roll_radius = 0.1
        profile.offset_extra = material_allowance if rough else 0.0
        profile.cut_mode = Profile.PROFILE_CLIMB if rough else Profile.PROFILE_CONVENTIONAL
        if name != None:
            profile.title = name
            profile.title_made_from_id = False
            
        if add_tags:
            offset_curve = geom.Curve(curve)
            offset_curve.Offset(-radius)
            box = offset_curve.GetBox()
            left = box.MinX() - 1.0
            right = box.MaxX() + 1.0
            if box.Height() < (2 * self.tag_y_margin + self.tag_width):
                # 2 tags in the middle
                y_mid = (box.MinY() + box.MaxY()) * 0.5
                lines = [ [ [left, y_mid], [right, y_mid] ], [[right, y_mid], [left, y_mid]] ]
            else:
                # 4 tags
                y_upper = box.MaxY() - self.tag_y_margin
                y_lower = box.MinY() + self.tag_y_margin
                lines = [ [ [left, y_upper], [right, y_upper] ], [[right, y_upper], [left, y_upper]], [ [left, y_lower], [right, y_lower] ], [[right, y_lower], [left, y_lower]] ]
            for line in lines:
                p = FindTagPoint(offset_curve, line)
                if p != None:
                    tag = Tag.Tag()
                    tag.width = self.tag_width
                    tag.height = self.tag_height
                    tag.angle = self.tag_angle
                    tag.pos = p
                    cad.PyIncref(tag)
                    if profile.tags == None:
                        tags = Tags.Tags()
                        cad.PyIncref(tags)
                        profile.Add(tags)
                        profile.tags = tags
                    profile.tags.Add(tag)

        if store_ops:
            self.stored_ops.append(profile)
        else:
            cad.AddUndoably(profile, wx.GetApp().program.operations)

    def ProfileCurve(self, curve, z_top = 0.0, z_bottom = None, move_start_type = MOVE_START_NOT, bottom_style = BOTTOM_THROUGH, add_tags = False, inside = False, do_finish_pass = False, store_ops = False, name = None):
            if z_bottom == None:
                cut_depth = self.thickness
                z_bottom = -self.thickness

            cut_depth = z_top - z_bottom
            
            profile_cutters = self.GetSortedCutters(cut_depth)
            
            if len(profile_cutters) == 0:
                self.failure = 'no cutters for ProfileCurve'
                return
            
            cutter_index = profile_cutters[0]
            
            self.ProfileCurveWithCutter(curve, cutter_index, z_top, z_bottom, move_start_type, bottom_style, 0.1 if do_finish_pass else 0.0, True, add_tags, Profile.PROFILE_RIGHT_OR_INSIDE if inside else Profile.PROFILE_LEFT_OR_OUTSIDE, store_ops = store_ops, name = name)
            if do_finish_pass:
                self.ProfileCurveWithCutter(curve, cutter_index, z_top, z_bottom, move_start_type, bottom_style, 0.0, False, add_tags, Profile.PROFILE_RIGHT_OR_INSIDE if inside else Profile.PROFILE_LEFT_OR_OUTSIDE, store_ops = store_ops, name = name + ' Finish Pass')
                
            
            # remove the first cutter
            profile_cutters.pop(0)
            
            area = geom.Area()
            if inside:
                curve.Reverse()
            area.Append(curve)
            
            cutter_radius = self.slot_cutters.tools[cutter_index].diam * 0.5

            copy_area = geom.Area(area)

            if inside:
                copy_area.Offset(cutter_radius)
                copy_area.Offset(-cutter_radius - 0.1)
            else:
                area.Offset(-cutter_radius)
                area.Offset(cutter_radius + 0.1)

            area.Subtract(copy_area)
            
            self.RestMachine(area, profile_cutters, z_top, z_bottom, bottom_style, do_finish_pass, store_ops, name = name + ' Rest Machining')

    def RestMachine(self, area, cutters, z_top, z_bottom, bottom_style, do_finish_pass, store_ops = False, name = None):
        # cut what's left
        if len(cutters) == 0:
            return

        # store area remaining to be cut, starting with the machining area's area
        area_remaining = geom.Area(area)
        
        for cutter_index in cutters:
            if area_remaining.NumCurves() == 0:
                # nothing left to cut
                break            
                    
            # ignore cutters not marked for rest_machining
            if not self.slot_cutters.tools[cutter_index].rest_machining:
                continue
            
            # start with the remaining area
            a = geom.Area(area_remaining)
            
            cutter_radius = self.slot_cutters.tools[cutter_index].diam * 0.5

            a.Thicken(0.1) # make sausages
            a.FitArcs()
            a.UnFitArcs()
            a.Intersect(self.area_done) # just keep the bits that are in the material
            a.Offset(-cutter_radius * 2 - 1) # offset sausage by tool diameter
            a.FitArcs()
            a.UnFitArcs()
            a2 = geom.Area(area_remaining) # take the original
            a2.Offset(-cutter_radius - 1) # offset it by overlap ( must be at least cutter radius, or peninsulas don't get machined )
            a.FitArcs()
            a.UnFitArcs()
            a.Union(a2) # join with sausage
            
            # subtract area already done ( areas above this one )
            a.Subtract(self.area_done)
            a_pointy = geom.Area(a) # remember pointy
            
            # offset it inwards and outwards to remove pointless small bits
            a.Offset(cutter_radius)
            a.Offset(-cutter_radius)   
            a.FitArcs()
            a.UnFitArcs()
            
            # calculate finishing pass; it's the sections of the pocket curves which touch the area done
            if do_finish_pass:
                finish_pass_area = geom.Area(a)
                finish_pass_area.Offset(cutter_radius)
                offset_area_done = geom.Area(self.area_done)
                offset_area_done.Offset(-cutter_radius - 0.2)
                finish_passes = []
                for curve in finish_pass_area.GetCurves():
                    curve.Reverse()
                    finish_passes += offset_area_done.InsideCurves(curve)
            
            sub_areas = a.Split()         

            for sub_a in sub_areas:
                if self.PocketCanBeDoneWithProfileOp(sub_a, cutter_index):
                    self.ProfileCurveWithCutter(sub_a.GetCurves()[0], cutter_index = cutter_index, z_top = z_top, z_bottom = z_bottom, bottom_style=bottom_style, material_allowance = 0.1 if do_finish_pass else 0.0, rough = True, side = Profile.PROFILE_RIGHT_OR_INSIDE, store_ops = store_ops, name = name)
                else:
                    self.PocketArea(sub_a, cutter_index, z_top = z_top, z_bottom = z_bottom, bottom_style=bottom_style, material_allowance = 0.1 if do_finish_pass else 0.0, store_ops = store_ops, name = name)
                    
            if do_finish_pass:
                for curve in finish_passes:
                    self.ProfileCurveWithCutter(curve, cutter_index = cutter_index, z_top = z_top, z_bottom = z_bottom, bottom_style=bottom_style, material_allowance = 0.1 if do_finish_pass else 0.0, rough = False, side = Profile.PROFILE_ON, store_ops = store_ops, name = None if (name == None) else (name + ' Finish Pass'))
                                    
            # calculate the remaining area
            a.Offset(-0.1) # imagine we cut more than we did, to cope with the arc vectors
            area_remaining.Subtract(a)        
        
    def PocketArea(self, a, cutter_index, z_top = 0.0, z_bottom = None, bottom_style = BOTTOM_NORMAL, material_allowance = 0.1, store_ops = False, name = None):
        tool_radius = self.slot_cutters.tools[cutter_index].diam * 0.5

        # test to see if area would disappear when offset inwards
        check_area = geom.Area(a)
        check_area.Offset(tool_radius)
        if check_area.NumCurves() == 0:
            # there is no point pocketing this area as there would be no toolpath
            return
         
        # add the sketch to pocket or profile
        sketch = cad.NewSketchFromArea(a)
        sketch.SetVisible(self.geometry_visible)
        cad.AddUndoably(sketch)
        
        # add the tool
        tool_id, default_tool = self.slot_cutters.AddIfNotAdded(cutter_index)
        
        pocket = Pocket.Pocket(sketch.GetID())
        pocket.tool_number = tool_id
        pocket.step_over = tool_radius
        pocket.start_depth = z_top
        pocket.final_depth = z_bottom
        pocket.material_allowance = material_allowance
        pocket.horizontal_feed_rate = default_tool.hfeed
        pocket.vertical_feed_rate = default_tool.vfeed
        pocket.spindle_speed = default_tool.spin
        pocket.step_down = default_tool.rough_step_down
        pocket.pattern = 0
        pocket.surface = 0
        if name != None:
            pocket.title = name + ' Area Clear'
            pocket.title_made_from_id = False
        
        self.SetDepthOpBottomFromStyle(pocket, bottom_style)

        if store_ops:
            self.stored_ops.append(pocket)
        else:
            cad.AddUndoably(pocket, wx.GetApp().program.operations)

    def SetDepthOpBottomFromStyle(self, depthop, bottom_style):
        if bottom_style == BOTTOM_THROUGH:
            depthop.z_thru_depth = 1.0 # to do, use more of the tool?
        elif bottom_style == BOTTOM_POCKET:
            depthop.z_finish_depth = 0.1

    def ClearProgram(self):
        if self.failure:
            return
        
        # check if there are any exisiting operations in the program
        if wx.GetApp().program.operations.GetNumChildren() > 0:
            if wx.MessageBox('The program already has operations. Do you want to continue and overwrite them?', style = wx.YES_NO) != wx.YES:
                return
        
        for object in wx.GetApp().program.tools.GetChildren():
            cad.DeleteUndoably(object)
        for object in wx.GetApp().program.patterns.GetChildren():
            cad.DeleteUndoably(object)
        for object in wx.GetApp().program.surfaces.GetChildren():
            cad.DeleteUndoably(object)
        for object in wx.GetApp().program.stocks.GetChildren():
            cad.DeleteUndoably(object)
        for object in wx.GetApp().program.operations.GetChildren():
            cad.DeleteUndoably(object)
        blank_nc = NcCode.NcCode()
        cad.PyIncref(blank_nc)
        wx.GetApp().CopyUndoably(wx.GetApp().program.nccode, blank_nc)
        
    def AddStockOfThickness(self, thickness):
        cuboid = step.NewCuboid()
        cuboid.width = self.part_box.Width() + 2 * self.x_margin
        cuboid.height = self.part_box.Height() + 2 * self.y_margin
        cuboid.depth = thickness
        mat = geom.Matrix()
        mat.Translate(geom.Point3D(0,0,-thickness))
        cuboid.Transform(mat)
        cuboid.SetVisible(False)
        cad.AddUndoably(cuboid)
        new_stock = Stock.Stock()
        new_stock.solids.append(cuboid.GetID())
        cad.AddUndoably(new_stock, wx.GetApp().program.stocks)
        self.thickness = thickness
        self.stock = cuboid
        
    def AddStock(self):
        if self.failure: return
        
        self.part_box = self.part.GetBox()
        if not self.material in self.stock_thicknesses:
            self.failure = 'material not found in stock: ' + self.material
            return
            
        thicknesses = self.stock_thicknesses[self.material]
        if len(thicknesses) == 0:
            self.failure = 'no stock available for material, material: ' + self.material
            return
        
        if self.use_part_thickness:
            self.AddStockOfThickness(self.part_box.Depth())
            return
        else:
            for thickness in thicknesses:
                if thickness >= self.part_box.Depth() - self.precision:
                    self.AddStockOfThickness(thickness)
                    return
            
        self.failure = 'part too thick to make: material: ' + self.material + ', part thickness: ' + str(self.part_box.Depth()) + ', thickest stock available: ' + str(thicknesses[-1])
                
    def MovePart(self):
        if self.failure: return
        part_box = self.part.GetBox()
        mat = geom.Matrix()
        # move down with bottom left corner at x_margin, y_margin and z top at z0
        mat.Translate(geom.Point3D(self.x_margin - part_box.MinX(), self.y_margin - part_box.MinY(), -part_box.MinZ() - self.thickness))
        cad.TransformUndoably(self.part, mat)
            
    def GetPart(self):
        for object in cad.GetObjects():
            if object.GetIDGroupType() == cad.OBJECT_TYPE_STL_SOLID and object.GetVisible():
                self.part = object
                break
        if self.part == None:
            self.failure = 'No Solid Found!'
       
    def MakeStockArea(self, a, extra_xminus, extra_yminus, extra_xplus, extra_yplus):
        box = a.GetBox()
        stock_area = geom.Area()
        c = geom.Curve()
        x0 = box.MinX() - math.fabs(extra_xminus)
        x1 = box.MaxX() + math.fabs(extra_xplus)
        y0 = box.MinY() - math.fabs(extra_yminus)
        y1 = box.MaxY() + math.fabs(extra_yplus)
        c.Append(geom.Point(x0, y0))
        c.Append(geom.Point(x1, y0))
        c.Append(geom.Point(x1, y1))
        c.Append(geom.Point(x0, y1))
        c.Append(geom.Point(x0, y0))
        stock_area.Append(c)
        return stock_area        

    def GetMaxOutsideDiameter(self):
        max_diameter = None
        for curve in self.shadow.GetCurves():
            if not curve.IsClockwise():
                r = curve.GetMaxCutterRadius()
                if r != None:
                    d = r * 2
                    if max_diameter == None or d < max_diameter:
                        max_diameter = d
        return max_diameter
    
    def GetMaxPocketCutterRadius(self, area):
        max_diam = None
        for curve in area.GetCurves():
            outer = curve.IsClockwise()
            diam = curve.GetMaxCutterRadius(outer, self.precision)
            if (diam != None) and (max_diam == None or diam < max_diam):
                max_diam = diam
        if max_diam != None:
            max_diam -= 0.11 # make sure there is room to offset the area inwards without it disappearing, also with room for a roughing pass
        return max_diam
    
    def PocketCanBeDoneWithProfileOp(self, a, cutter_index):
        # if the area is a simple single curve and disappears when offset inwards by the cutter diameter, then it's fine to just profile the area
        if a.NumCurves() == 1:
            a_copy = geom.Area(a)
            a_copy.Offset(self.slot_cutters.tools[cutter_index].diam * 0.95)
            if a_copy.NumCurves() == 0:
                return True
        
        return False
        
    def GetSortedCutters(self, cut_depth, rest_machining = False):
        return self.slot_cutters.GetSortedCutters(cut_depth, max_cutter_diameter = None if self.big_rigid_part else BIG_CUTTER_DIAMETER, rest_machining = rest_machining)

class AvailableTool:
    def __init__(self, diam, type, rest_machining, cutting_length, hfeed, finish_hfeed, spin, vfeed, rough_step_down, finish_step_down = None):
        self.diam = diam
        self.type = type
        self.rest_machining = rest_machining
        self.cutting_length = cutting_length
        self.hfeed = hfeed
        if hfeed == None:
            self.hfeed = 200.0
        self.finish_hfeed = finish_hfeed
        self.spin = spin
        self.vfeed = vfeed
        self.rough_step_down = rough_step_down
        self.finish_step_down = finish_step_down
        self.added_tool_id = None
        
    def GetName(self):
        if self.type == TOOL_TYPE_SLOTCUTTER:
            return str(self.diam) + ' mm Slot Cutter'
        elif self.type == TOOL_TYPE_DRILL:
            return str(self.diam) + ' mm Drill'
        else:
            return 'Unknown Tool Type'
        
    def NewTool(self, tool_number):
        tool = Tool.Tool(self.diam, title = self.GetName(), tool_number = tool_number, type = self.type)
        cad.PyIncref(tool)
        self.added_tool_id = tool_number
        return tool
        
class AvailableTools:
    def __init__(self, auto_program, name, tool_numbers):
        self.auto_program = auto_program
        self.name = name
        self.tools = []
        self.tool_numbers = tool_numbers
        self.next_index = 0
        
    def ImportToolsForMaterial(self, material):
        self.tools = []
        import xml.etree.ElementTree as ET
        import os
        this_dir = os.path.dirname(os.path.realpath(__file__))
        path = this_dir + '/available.tools'
        tree = ET.parse(path)
        root = tree.getroot()
        for child in root:
            if (child.tag == 'material') and (child.attrib['name'].lower() == material): 
                for child in child:
                    name = child.tag
                    name = name.replace('_', ' ')
                    if name == self.name:
                        for child in child:
                            if child.tag == 'tool':
                                diam = 0.0
                                type = TOOL_TYPE_UNDEFINED
                                rest_machining = False
                                cutting_length = 0.0
                                hfeed = 0.0
                                finish_hfeed = 0.0
                                spin = 0.0
                                vfeed = 0.0
                                rough_step_down = 0.0
                                finish_step_down = 0.0
                                active = True
                                if 'active' in child.attrib:
                                    active = eval(child.attrib['active'])
                                if active:
                                    if 'diam' in child.attrib:
                                        diam = float(child.attrib['diam'])
                                    if 'type' in child.attrib:
                                        type = eval(child.attrib['type'])
                                    if 'rest_machining' in child.attrib:
                                        rest_machining = eval(child.attrib['rest_machining'])
                                    if 'cutting_length' in child.attrib:
                                        cutting_length = float(child.attrib['cutting_length'])
                                    if 'hfeed' in child.attrib:
                                        hfeed = float(child.attrib['hfeed'])
                                    if 'finish_hfeed' in child.attrib:
                                        finish_hfeed = float(child.attrib['finish_hfeed'])
                                    if 'spin' in child.attrib:
                                        spin = float(child.attrib['spin'])
                                    if 'vfeed' in child.attrib:
                                        vfeed = float(child.attrib['vfeed'])
                                    if 'rough_step_down' in child.attrib:
                                        rough_step_down = float(child.attrib['rough_step_down'])
                                    if 'finish_step_down' in child.attrib:
                                        finish_step_down = float(child.attrib['finish_step_down'])
                                    self.tools.append(AvailableTool(diam, type, rest_machining, cutting_length, hfeed, finish_hfeed, spin, vfeed, rough_step_down, finish_step_down))
        
    def AddIfNotAdded(self, tool_index):
        tool = self.tools[tool_index]
        if tool.added_tool_id != None:
            return tool.added_tool_id, tool
        if self.next_index >= len(self.tool_numbers):
            self.failure = 'no more ' + self.name + ' available!\ntrying to add: ' + self.tools[tool_index].GetName()
            tool_id = 0
        else:
            tool_id = self.tool_numbers[self.next_index]
            self.next_index += 1
            self.auto_program.tools_to_add_at_end[tool_id] = tool.NewTool(tool_id)        
        return tool_id, tool
    
    def GetToolOfDiameter(self, d, cut_depth, precision):
        for index in range(0, len(self.tools)):
            if self.tools[index].cutting_length < cut_depth:
                continue
            tool_diameter = self.tools[index].diam
            if math.fabs(tool_diameter - d) < precision:
                return index
        return None
    
    def GetDiamMapShortest(self, cut_depth, max_cutter_diameter, rest_machining):
        # map of diameter to found index for checking smallest cutter length
        index = 0
        diam_map = {} # map of diameter to found index for checking smallest cutter length
        for tool in self.tools:
            if max_cutter_diameter == None or max_cutter_diameter >= tool.diam:
                if (tool.cutting_length >= cut_depth) and ((rest_machining == False) or (tool.rest_machining == True)):
                    if tool.diam in diam_map:
                        # tool diameter already in map
                        existing_tool = self.tools[diam_map[tool.diam]]
                        if tool.cutting_length < existing_tool.cutting_length:
                            # replace map enty with shorter tool
                            diam_map[tool_diam] = index
                    else:
                        diam_map[tool.diam] = index
            index += 1
        return diam_map
            
    def GetSortedCutters(self, cut_depth, max_cutter_diameter, rest_machining):
        diam_map = self.GetDiamMapShortest(cut_depth, max_cutter_diameter, rest_machining)
            
        # make the list from the map
        cutters = []
        for d in sorted(diam_map.keys(), reverse = True):
            cutters.append(diam_map[d])
        return cutters

hash_axis = None
hash_axis2 = None
 
def xyhash(p):
    global hash_axis
    global hash_axis2
    dx = p * hash_axis
    dy = p * hash_axis2
    return dx + dy*1000.0

class Hole:
    # used to group found features
    def __init__(self, circle, top_z, bottom_z):
        self.diameter = circle.radius * 2
        self.top_z = top_z
        self.bottom_z = bottom_z
        self.pts = [circle.c]
        
    def AddHole(self, hole, precision):
        # returns True if it added the hole's position to this hole
        if math.fabs(self.diameter - hole.diameter) > precision:
            return False
        if math.fabs(self.top_z - hole.top_z) > precision:
            return False
        if math.fabs(self.bottom_z - hole.bottom_z) > precision:
            return False
        self.pts += hole.pts
        return True
    
    
    def SortPoints2(self, axis):
        global hash_axis
        global hash_axis2
        hash_axis = axis
        hash_axis2 = ~axis
        
        self.pts.sort(key = xyhash)
    
    def SortPoints(self):
        box = geom.Box()
        for pt in self.pts:
            box.InsertPoint(pt)
            
        if box.Width() > box.Height():
            self.SortPoints2(geom.Point(1,0))
        else:
            self.SortPoints2(geom.Point(0,1))
    
    def __str__(self):
        return 'Hole - diameter = ' + str(self.diameter) + ' at pts: ' + str(self.pts)

def FindTagPoint(curve, line):
    # line defined by two lists of two coordinates
    c2 = geom.Curve()
    c2.Append(geom.Point(line[0][0], line[0][1]))
    c2.Append(geom.Point(line[1][0], line[1][1]))
    pts = curve.Intersections(c2)
    if len(pts) == 0:
        return None
    return pts[0]

def start_pycad(a):
    import subprocess
    subprocess.call(['C:\\Users\\Dan Heeks\\AppData\\Local\\Programs\\Python\\Python36-32\\python', 'viewer.py', 'c:\\tmp\\sketch.dxf'], cwd = 'C:\\Dev\\AutoProgram')
    import os
    os.remove('c:\\tmp\\area_str.txt')        
        
def area_str(self):
    self.WriteDxf('c:\\tmp\\sketch.dxf')

    try:
        f = open('c:\\tmp\\area_str.txt', 'rb')
        f.close()
    except:
        f = open('c:\\tmp\\area_str.txt', 'wb')
        f.close()
    
        import _thread
        _thread.start_new_thread(start_pycad, (self,))
    return 'ok'

def curve_str(self):
    area = geom.Area()
    area.Append(self)
    return str(area)
    
import platform
if platform.system() == 'Windows':
    geom.Area.__str__ = area_str
    geom.Curve.__str__ = curve_str

def AddSketch(a):
    sketch = cad.NewSketchFromArea(self.shadow)
    sketch.SetTitle('Debug Sketch')
    cad.AddUndoably(sketch)
    