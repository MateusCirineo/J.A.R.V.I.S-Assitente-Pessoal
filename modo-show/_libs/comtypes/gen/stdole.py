from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    OLE_CANCELBOOL, Font, OLE_YPOS_HIMETRIC, DISPMETHOD, Checked,
    StdPicture, Gray, VgaColor, DISPPROPERTY, _lcid, GUID,
    IEnumVARIANT, FONTSTRIKETHROUGH, OLE_OPTEXCLUSIVE, Library,
    OLE_YPOS_CONTAINER, VARIANT_BOOL, IFontEventsDisp, FONTBOLD,
    OLE_YSIZE_HIMETRIC, OLE_XSIZE_PIXELS, IUnknown, CoClass,
    Unchecked, FONTNAME, Color, FONTSIZE, OLE_YSIZE_PIXELS,
    FONTUNDERSCORE, dispid, StdFont, FONTITALIC, Default, COMMETHOD,
    IDispatch, OLE_HANDLE, DISPPARAMS, OLE_YSIZE_CONTAINER, OLE_COLOR,
    OLE_XPOS_HIMETRIC, EXCEPINFO, IPicture, typelib_path, HRESULT,
    FontEvents, Picture, OLE_XSIZE_HIMETRIC, OLE_XPOS_CONTAINER,
    OLE_XSIZE_CONTAINER, BSTR, _check_version, IFontDisp,
    OLE_ENABLEDEFAULTBOOL, IFont, IPictureDisp, OLE_YPOS_PIXELS,
    OLE_XPOS_PIXELS, Monochrome
)


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


__all__ = [
    'OLE_CANCELBOOL', 'FONTITALIC', 'Font', 'Default', 'OLE_HANDLE',
    'OLE_YPOS_HIMETRIC', 'OLE_YSIZE_CONTAINER', 'OLE_COLOR',
    'OLE_TRISTATE', 'OLE_XPOS_HIMETRIC', 'Checked', 'IPicture',
    'StdPicture', 'Gray', 'VgaColor', 'typelib_path', 'FontEvents',
    'LoadPictureConstants', 'FONTSTRIKETHROUGH', 'OLE_OPTEXCLUSIVE',
    'Picture', 'OLE_YPOS_CONTAINER', 'Library', 'OLE_XSIZE_HIMETRIC',
    'OLE_XPOS_CONTAINER', 'IFontEventsDisp', 'FONTBOLD',
    'OLE_YSIZE_HIMETRIC', 'OLE_XSIZE_PIXELS', 'OLE_XSIZE_CONTAINER',
    'Unchecked', 'FONTNAME', 'Color', 'FONTSIZE',
    'OLE_ENABLEDEFAULTBOOL', 'IFont', 'IPictureDisp', 'IFontDisp',
    'OLE_YPOS_PIXELS', 'OLE_XPOS_PIXELS', 'OLE_YSIZE_PIXELS',
    'FONTUNDERSCORE', 'Monochrome', 'StdFont'
]

