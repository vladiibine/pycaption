import unittest
from copy import deepcopy
from bs4 import BeautifulSoup

from pycaption.dfxp import (SinglePositioningDFXPWriter, DFXPReader,
                            DFXP_DEFAULT_REGION, DFXP_DEFAULT_REGION_ID)
from pycaption.geometry import HorizontalAlignmentEnum, VerticalAlignmentEnum


class SinglePositioningDFXPWRiterTestCase(unittest.TestCase):
    def test_only_the_default_region_is_created(self):
        caption_set = DFXPReader().read(SAMPLE_DFXP_MULTIPLE_REGIONS_OUTPUT)

        dfxp = SinglePositioningDFXPWriter().write(caption_set)

        layout = BeautifulSoup(dfxp, features='html.parser').findChild('layout')

        self.assertEqual(len(layout.findChildren('region')), 1)

    def test_only_the_default_region_is_referenced(self):

        caption_set = DFXPReader().read(SAMPLE_DFXP_MULTIPLE_REGIONS_OUTPUT)

        dfxp = SinglePositioningDFXPWriter().write(caption_set)

        soup = BeautifulSoup(dfxp, features='html.parser')

        for elem in soup.findAll():
            if 'region' in elem:
                self.assertEqual(elem['region'], DFXP_DEFAULT_REGION_ID)

    def test_only_the_custom_region_is_created(self):
        caption_set = DFXPReader().read(SAMPLE_DFXP_MULTIPLE_REGIONS_OUTPUT)

        # it's easier to copy this than create a new one
        new_region = deepcopy(DFXP_DEFAULT_REGION)
        new_region.alignment.horizontal = HorizontalAlignmentEnum.LEFT
        new_region.alignment.vertical = VerticalAlignmentEnum.TOP

        dfxp = SinglePositioningDFXPWriter(new_region).write(caption_set)

        layout = BeautifulSoup(dfxp, features='html.parser').findChild('layout')

        self.assertEqual(len(layout.findChildren('region')), 1)


SAMPLE_DFXP_MULTIPLE_REGIONS_OUTPUT = u"""\
<?xml version="1.0" encoding="utf-8"?>
<tt xml:lang="en" xmlns="http://www.w3.org/ns/ttml" xmlns:tts="http://www.w3.org/ns/ttml#styling">
 <head>
  <styling>
   <style tts:color="#ffeedd" tts:fontFamily="Arial" tts:fontSize="10pt" tts:textAlign="center" xml:id="p"/>
  </styling>
  <layout>
   <region tts:displayAlign="after" tts:textAlign="center" xml:id="bottom"/>
   <region tts:displayAlign="after" tts:extent="30px 40px" tts:origin="40px 50px" tts:textAlign="center" xml:id="r0"/>
   <region tts:displayAlign="after" tts:extent="50% 50%" tts:origin="10% 30%" tts:textAlign="center" xml:id="r1"/>
   <region tts:displayAlign="after" tts:padding="2c 2c 2c 2c" tts:textAlign="center" xml:id="r2"/>
   <region tts:displayAlign="after" tts:extent="3em 4em" tts:padding="3px 4px 5px 4px" tts:textAlign="center" xml:id="r3"/>
   <region tts:displayAlign="after" tts:textAlign="start" xml:id="r4"/>
  </layout>
 </head>
 <body>
  <div region="bottom" xml:lang="en-US">
   <p begin="00:00:02.700" end="00:00:05.700" region="r0" style="p">
    Hello there!
   </p>
   <p begin="00:00:05.700" end="00:00:06.210" region="r1" style="p">
    How are you?
   </p>
   <p begin="00:00:07.700" end="00:00:09.210" region="r2" style="p">
    &gt;&gt; I'm fine, thank you &lt;&lt; replied someone.<span region="r1">&gt;&gt;And now we're going to have fun&lt;&lt;</span>
   </p>
   <p begin="00:00:10.707" end="00:00:11.210" region="r3" style="p">
    What do you have in mind?
   </p>
   <p begin="00:00:12.900" end="00:00:13.900" region="r4" style="p" tts:textAlign="start">
    To write random words here!
   </p>
  </div>
 </body>
</tt>"""