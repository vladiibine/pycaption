from ..exceptions import CaptionReadSyntaxError


class _PositioningTracker(object):
    """Helps determine the positioning of a node, having kept track of
    positioning-related commands.

    Acts like a state-machine, with 2

    """
    def __init__(self, positioning=None):
        """
        :param positioning: positioning information (row, column)
        :type positioning: tuple[int]
        """
        self._positions = [positioning]
        self._break_required = False
        self._repositioning_required = False

    def update_positioning(self, positioning):
        """Being notified of a position change, updates the internal state,
        to as to be able to tell if it was a trivial change (a simple line
        break) or not.

        :type positioning: tuple[int]
        :param positioning: a tuple (row, col)
        """
        current = self._positions[-1]

        if not current:
            if positioning:
                # set the positioning for the first time
                self._positions = [positioning]
            return

        row, col = current
        new_row, _ = positioning

        # is the new position simply one line below?
        if new_row == row + 1:
            self._positions.append((new_row, col))
            self._break_required = True
        else:
            # reset the "current" position altogether.
            self._positions = [positioning]
            self._repositioning_required = True

    def get_current_position(self):
        """Returns the current usable position

        :rtype: tuple[int]

        :raise: CaptionReadSyntaxError
        """
        if not any(self._positions):
            raise CaptionReadSyntaxError(
                u'No Preamble Address Code [PAC] was provided'
            )
        else:
            return self._positions[0]

    def is_repositioning_required(self):
        """Determines whether the current positioning has changed non-trivially

        Trivial would be mean that a line break should suffice.
        :rtype: bool
        """
        return self._repositioning_required

    def acknowledge_position_changed(self):
        """Acknowledge the position tracer that the position was changed
        """
        self._repositioning_required = False

    def is_linebreak_required(self):
        """If the current position is simply one line below the previous.
        :rtype: bool
        """
        return self._break_required

    def acknowledge_linebreak_consumed(self):
        """Call to acknowledge that the line required was consumed
        """
        self._break_required = False


class DefaultProvidingPositionTracker(_PositioningTracker):
    """A _PositioningTracker that provides if needed a default value (14, 0), or
    uses the last positioning value set anywhere in the document
    """
    default = (14, 0)

    def __init__(self, positioning=None, default=None):
        """
        :type positioning: tuple[int]
        :param positioning: a tuple of ints (row, column)

        :type default: tuple[int]
        :param default: a tuple of ints (row, column) to use as fallback
        """
        super(DefaultProvidingPositionTracker, self).__init__(positioning)

        if default:
            self.default = default

    def get_current_position(self):
        """Returns the currently tracked positioning, the last positioning that
        was set (anywhere), or the default it was initiated with

        :rtype: tuple[int]
        """
        try:
            return (
                super(DefaultProvidingPositionTracker, self).
                get_current_position()
            )
        except CaptionReadSyntaxError:
            return self.default

    def update_positioning(self, positioning):
        """If called, sets this positioning as the default, then delegates
        to the super class.

        :param positioning: a tuple of ints (row, col)
        :type positioning: tuple[int]
        """
        if positioning:
            self.default = positioning

        super(DefaultProvidingPositionTracker, self).update_positioning(
            positioning)

    @classmethod
    def reset_default_positioning(cls):
        """Resets the previous default value to the original (14, 0)

        When the context changes (a new caption is being processed, the
        default positioning must NOT be carried over). Needed because we store
        information at the class level.
        """
        cls.default = (14, 0)


class DefaultProvidingItalicsTracker(object):
    """State machine-like object, that keeps track of the required italic state
    of the caption text.
    """
    def __init__(self, default=False):
        self._value = default
        self._switched_off_count = False
        self._switched_on_count = False

    def command_on(self):
        """Marks the requirement to begin italicising text
        """
        if not self._value:
            self._switched_on_count = True

        self._value = True

    def command_off(self):
        """Marks the requirement to end italicising the text
        """
        if self._value:
            self._switched_off_count = True

        self._value = False

    def acknowledge_switched(self, on=True):
        if on:
            self._switched_on_count = False
        else:
            self._switched_off_count = False

    def can_end_italics(self):
        """Return True if the italics state is on, or if the consumer has
        never acknowledged having turned off the italics

        :rtype: bool
        """
        return self._switched_on_count

    def is_on(self):
        return self._value and not self._switched_on_count

    def should_confirm_on(self):
        return self._switched_on_count

    def should_confirm_off(self):
        return self._switched_off_count

    def state_changed(self):
        return self._switched_off_count or self._switched_on_count