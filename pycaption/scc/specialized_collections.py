from ..base import Caption, CaptionNode
from ..geometry import UnitEnum, Size, Layout, Point

from .constants import PAC_BYTES_TO_POSITIONING_MAP, COMMANDS


class TimingCorrectingCaptionList(list):
    """List of captions. Will know to correct the last caption's end time
    when adding a new caption.

    Also, doesn't allow Nones or empty captions
    """
    def append(self, p_object):
        """When appending a new caption to the list, make sure the last one
        has an end. Also, don't add empty captions

        :type p_object: Caption
        """
        if p_object is None:
            return

        if len(self) > 0 and self[-1].end == 0:
            self[-1].end = p_object.start

        if p_object.nodes:
            super(TimingCorrectingCaptionList, self).append(p_object)

    def extend(self, iterable):
        """Adds the elements in the iterable to the list

        :param iterable: any iterable
        """
        for elem in iterable:
            self.append(elem)


class NotifyingDict(dict):
    """Dictionary-like object, that treats one key as 'active',
    and notifies observers if the active key changed
    """
    # Need an unhashable object as initial value for the active key.
    # That way we're sure this was never a key in the dict.
    _guard = {}

    def __init__(self, *args, **kwargs):
        super(NotifyingDict, self).__init__(*args, **kwargs)
        self.active_key = self._guard
        self.observers = []

    def set_active(self, key):
        """Sets the active key

        :param key: any hashable object
        """
        if key not in self:
            raise ValueError(u'No such key present')

        # Notify observers of the change
        if key != self.active_key:
            for observer in self.observers:
                observer(self.active_key, key)

        self.active_key = key

    def get_active(self):
        """Returns the value corresponding to the active key
        """
        if self.active_key is self._guard:
            raise KeyError(u'No active key set')

        return self[self.active_key]

    def add_change_observer(self, observer):
        """Receives a callable function, which it will call if the active
        element changes.

        The observer will receive 2 positional arguments: the old and new key

        :param observer: any callable that can be called with 2 positional
            arguments
        """
        if not callable(observer):
            raise TypeError(u'The observer should be callable')

        self.observers.append(observer)


class CaptionCreator(object):
    """Creates and maintains a collection of Captions
    """
    def __init__(self):
        self._collection = TimingCorrectingCaptionList()

        # subset of self._collection;
        # captions here will be susceptible to time corrections
        self._still_editing = []

    def correct_last_timing(self, end_time, force=False):
        """Called to set the time on the last Caption(s) stored with no end
        time

        :type force: bool
        :param force: Set the end time even if there's already an end time

        :type end_time: int
        :param end_time: microseconds; the end of the caption;
        """
        if not self._still_editing:
            return

        if force:
            captions_to_correct = self._still_editing
        else:
            captions_to_correct = (
                caption for caption in self._still_editing
                if caption.end == 0
            )

        for caption in captions_to_correct:
            caption.end = end_time

    def create_and_store(self, node_buffer, start):
        """Interpreter method, will convert the buffer into one or more Caption
        objects, storing them internally.

        :type node_buffer: InterpretableNodeCreator

        :type start: int
        :param start: the start time in microseconds
        """
        if node_buffer.is_empty():
            return

        caption = Caption()
        caption.start = start
        caption.end = 0  # Not yet known; filled in later
        self._still_editing = [caption]

        open_italic = False

        for element in node_buffer:
            # skip empty elements
            if element.is_empty():
                continue

            elif element.requires_repositioning():
                self._remove_extra_italics(caption)
                open_italic = False
                caption = Caption()
                caption.start = start
                caption.end = 0
                self._still_editing.append(caption)

            # handle line breaks
            elif element.is_explicit_break():
                new_nodes = self._translate_break(open_italic)
                open_italic = False
                caption.nodes.extend(new_nodes)

            # handle open italics
            elif element.sets_italics_on():
                # add italics
                caption.nodes.append(
                    CaptionNode.create_style(True, {u'italics': True}))
                # open italics, no longer first element
                open_italic = True

            # handle clone italics
            elif element.sets_italics_off() and open_italic:
                caption.nodes.append(
                    CaptionNode.create_style(False, {u'italics': True}))
                open_italic = False

            # handle text
            elif element.is_text_node():
                # add text
                layout_info = _get_layout_from_tuple(element.position)
                caption.nodes.append(
                    CaptionNode.create_text(
                        element.get_text(), layout_info=layout_info),
                )
                caption.layout_info = layout_info

        # close any open italics left over
        if open_italic:
            caption.nodes.append(
                CaptionNode.create_style(False, {u'italics': True}))

        # remove extraneous italics tags in the same caption
        self._remove_extra_italics(caption)

        self._collection.extend(self._still_editing)

    @staticmethod
    def _translate_break(open_italic):
        """Depending on the context, translates a line break into one or more
        nodes, returning them.

        :param open_italic: bool
        :rtype: tuple
        """
        new_nodes = []

        if open_italic:
            new_nodes.append(CaptionNode.create_style(
                False, {u'italics': True}))

        # add line break
        new_nodes.append(CaptionNode.create_break())

        return new_nodes

    @staticmethod
    def _remove_extra_italics(caption):
        """Legacy logic slightly refactored. Removes STYLE nodes that would
        surround a BREAK node.

        See CaptionNode

        :type caption: Caption
        """
        i = 0
        length = max(0, len(caption.nodes) - 2)
        while i < length:
            if (caption.nodes[i].type_ == CaptionNode.STYLE and
                    caption.nodes[i].content[u'italics'] and
                    caption.nodes[i + 1].type_ == CaptionNode.BREAK and
                    caption.nodes[i + 2].type_ == CaptionNode.STYLE and
                    caption.nodes[i + 2].content[u'italics']):
                # Remove the two italics style nodes
                caption.nodes.pop(i)
                caption.nodes.pop(i + 1)
                length -= 2
            i += 1

    def get_all(self):
        """Returns the Caption collection as a list

        :rtype: list
        """
        return list(self._collection)


class InterpretableNodeCreator(object):
    """Creates _InterpretableNode instances from characters and commands,
    and stores them internally in a buffer.
    """
    def __init__(self, collection=None, italics_tracker=None,
                 position_tracker=None):
        """
        :param collection: an optional collection of nodes

        :type italics_tracker: .state_machines.DefaultProvidingItalicsTracker
        :param italics_tracker: object that cna be interrogated to get the
            italics state of the nodes we're creating (whether italics
            should be on or off)

        :param position_tracker:
        :return:
        """
        if not collection:
            self._collection = []
        else:
            self._collection = collection

        self._position_tracer = position_tracker
        self.italics_tracker = italics_tracker

    def is_empty(self):
        """Whether any text was added to the buffer
        """
        return not any(element.text for element in self._collection)

    def add_chars(self, *chars):
        """Adds characters to a text node (last text node, or a new one)

        :param chars: tuple containing text (unicode)
        """
        if not chars:
            return

        current_position = self._position_tracer.get_current_position()

        # get or create a usable node
        text_nodes = [
            elem_ for elem_ in self._collection if elem_.is_text_node()
        ]
        if text_nodes:
            node = text_nodes[-1]
        else:
            # create first node
            node = _InterpretableNode(position=current_position)
            self._collection.append(node)

        # handle a simple line break
        if self._position_tracer.is_linebreak_required():
            # must insert a line break here
            self._collection.append(_InterpretableNode.create_break(
                position=current_position))
            node = _InterpretableNode.create_text(current_position)
            self._collection.append(node)
            self._position_tracer.acknowledge_linebreak_consumed()

        # handle completely new positioning
        elif self._position_tracer.is_repositioning_required():
            # this node will have a different positioning than the previous one
            self._collection.append(
                _InterpretableNode.create_repositioning_command())
            node = _InterpretableNode.create_text(current_position)
            self._collection.append(node)
            self._position_tracer.acknowledge_position_changed()

        node.add_chars(*chars)

    def interpret_command(self, command):
        """Given a command determines whether tu turn italics on or off,
        or to set the positioning

        This is mostly used to convert from the legacy-style commands

        :type command: unicode
        """
        self._update_positioning(command)

        text = COMMANDS.get(command, u'')

        if u'<$>{italic}<$>' in text:
            self._collection.append(
                _InterpretableNode.create_italics_style(
                    self._position_tracer.get_current_position())
            )
        elif u'<$>{end-italic}<$>' in text:
            self._collection.append(
                _InterpretableNode.create_italics_style(
                    self._position_tracer.get_current_position(),
                    turn_on=False
                )
            )

    def _update_positioning(self, command):
        """Sets the positioning information to use for the next nodes

        :type command: unicode
        """
        if len(command) != 4:
            return

        first, second = command[:2], command[2:]

        try:
            positioning = PAC_BYTES_TO_POSITIONING_MAP[first][second]
        except KeyError:
            pass
        else:
            self._position_tracer.update_positioning(positioning)

    def __iter__(self):
        return iter(self._collection)

    @classmethod
    def from_list(cls, stash_list, italics_tracker, position_tracker):
        """Having received a list of instances of this class, creates a new
        instance that contains all the nodes of the previous instances
        (basically concatenates the many stashes into one)

        :type stash_list: list[InterpretableNodeCreator]
        :param stash_list: a list of instances of this class

        :type italics_tracker: .state_machines.DefaultProvidingItalicsTracker
        :param italics_tracker: state machine to be interrogated about
            the italics state when creating a node

        :type position_tracker: .state_machines.DefaultProvidingPositionTracker
        :param position_tracker: state machine to be interrogated about the
            positioning when creating a node

        :rtype: InterpretableNodeCreator
        """
        instance = cls(italics_tracker=italics_tracker,
                       position_tracker=position_tracker)
        new_collection = instance._collection

        for idx, stash in enumerate(stash_list):
            new_collection.extend(stash._collection)

            # use space to separate the stashes, but don't add final space
            if idx < len(stash_list) - 1:
                try:
                    instance._collection[-1].add_chars(u' ')
                except AttributeError:
                    pass

        return instance


def _get_layout_from_tuple(position_tuple):
    """Create a Layout object from the positioning information given

    The row can have a value from 1 to 15 inclusive. (vertical positioning)
    The column can have a value from 0 to 31 inclusive. (horizontal)

    :param position_tuple: a tuple of ints (row, col)
    :type position_tuple: tuple
    :rtype: Layout
    """
    if not position_tuple:
        return None

    row, column = position_tuple

    horizontal = Size(100 * column / 32.0, UnitEnum.PERCENT)
    vertical = Size(100 * (row - 1) / 15.0, UnitEnum.PERCENT)
    return Layout(origin=Point(horizontal, vertical))


class _InterpretableNode(object):
    """Value object, that can contain text information, or interpretable
    commands (such as explicit line breaks or turning italics on/off)
    """
    TEXT = 0
    BREAK = 1
    ITALICS_ON = 2
    ITALICS_OFF = 3
    CHANGE_POSITION = 4

    def __init__(self, text=None, position=None, type_=0):
        """
        :type text: unicode
        :param position: a tuple of ints (row, column)
        :param type_: self.TEXT | self.BREAK | self.ITALICS
        :type type_: int
        """
        self.text = text
        self.position = position
        self._type = type_

    def add_chars(self, *args):
        """This being a text node, add characters to it.
        :param args:
        :type args: tuple[unicode]
        :return:
        """
        if self.text is None:
            self.text = u''

        self.text += u''.join(args)

    def is_text_node(self):
        """
        :rtype: bool
        """
        return self._type == self.TEXT

    def is_empty(self):
        """
        :rtype: bool
        """
        if self._type == self.TEXT:
            return not self.text

        return False

    def is_explicit_break(self):
        """
        :rtype: bool
        """
        return self._type == self.BREAK

    def sets_italics_on(self):
        """
        :rtype: bool
        """
        return self._type == self.ITALICS_ON

    def sets_italics_off(self):
        """
        :rtype: bool
        """
        return self._type == self.ITALICS_OFF

    def requires_repositioning(self):
        """Whether the node must be interpreted as a change in positioning

        :rtype: bool
        """
        return self._type == self.CHANGE_POSITION

    def get_text(self):
        """A little legacy code.
        """
        return u' '.join(self.text.split())

    @classmethod
    def create_break(cls, position):
        """Create a node, interpretable as an explicit line break

        :type position: tuple[int]
        :param position: a tuple (row, col) containing the positioning info

        :rtype: _InterpretableNode
        """
        return cls(type_=cls.BREAK, position=position)

    @classmethod
    def create_text(cls, position, *chars):
        """Create a node interpretable as text

        :type position: tuple[int]
        :param position: a tuple (row, col) to mark the positioning

        :type chars: tuple[unicode]
        :param chars: characters to add to the text

        :rtype: _InterpretableNode
        """
        return cls(u''.join(chars), position=position)

    @classmethod
    def create_italics_style(cls, position, turn_on=True):
        """Create a node, interpretable as a command to switch italics on/off

        :type position: tuple[int]
        :param position: a tuple (row, col) to mark the positioning

        :type turn_on: bool
        :param turn_on: whether to turn the italics on or off

        :rtype: _InterpretableNode
        """
        return cls(
            position=position,
            type_=cls.ITALICS_ON if turn_on else cls.ITALICS_OFF
        )

    @classmethod
    def create_repositioning_command(cls):
        """Create node interpretable as a command to change the current
        position
        """
        return cls(type_=cls.CHANGE_POSITION)

    def __repr__(self):
        if self._type == self.BREAK:
            extra = u'BR'
        elif self._type == self.TEXT:
            extra = u'"{}"'.format(self.text)
        elif self._type in (self.ITALICS_ON, self.ITALICS_OFF):
            extra = u'italics {}'.format(
                u'on' if self._type == self.ITALICS_ON else u'off'
            )
        else:
            extra = u'change position'

        return u'<INode: {extra} >'.format(extra=extra)
