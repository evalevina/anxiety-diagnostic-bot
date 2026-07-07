from aiogram.fsm.state import StatesGroup, State


class QuizState(StatesGroup):
    waiting_phone = State()
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()


class BookingState(StatesGroup):
    waiting_time = State()
    waiting_concern = State()


class DiaryState(StatesGroup):
    waiting_note = State()
    waiting_custom_note = State()


class ReviewState(StatesGroup):
    waiting_text = State()


class ThoughtRecordState(StatesGroup):
    waiting_thought = State()
    waiting_distortion = State()
    waiting_reframe = State()
    waiting_rerate = State()
