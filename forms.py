from flask_wtf import FlaskForm as Form
from wtforms import StringField, SubmitField, SelectField, IntegerField, \
    TextAreaField, DateField, HiddenField
from wtforms.validators import DataRequired,  URL
from wtforms import validators
from wtforms.fields.html5 import EmailField


def get_datetime(name_field, id_field):
    return DateField(name_field, id=id_field, render_kw={
        "data-format": "dd.MM.yyyy hh:mm:ss", 'readonly': True,
        "style": "cursor: pointer; visibility: visible; opacity: 1;"},
        format='%d.%m.%Y %H:%M')


def get_activity():
    arr = ['Дизайн/Архитектор', 'Мебель', 'Потолки', 'Стенды', 'Реклама',
           'Строители']
    return [(name, name) for name in arr]


def get_segment():
    arr = ['Монтажники', 'Опт', 'Рынки/Магазины']
    return [(name, name) for name in arr]


class FormClientCard(Form):
    status = SelectField("Статус клиента",
                         choices=[('Потенциальный', 'Потенциальный'),
                                  ('Рабочий', 'Рабочий')])

    city = StringField('Город')

    segment = SelectField('Сегмент', choices=get_segment())

    activity = SelectField('Вид деятельности', choices=get_activity())

    loyalty = SelectField(
        """Лояльность клиента
        <span class="green"><i class="fa fa-square"></i></span> - Лояльный
        <span class="blue"><i class="fa fa-square"></i></span> - Нелояльный""",
        choices=[('Лояльный', 'Лояльный'), ('Нелояльный', 'Нелояльный')],
        description="Для цветовой идентификации лояльности клиента")

    company_name = StringField(
        'Название компании *',
        render_kw={"placeholder": 'Например, ООО "Ромашка"'},
        validators=[DataRequired()])

    site = StringField('Сайт', default='',
                       render_kw={"placeholder": "Например, http://romaska.ru"},
                       validators=[URL(message='Адрес сайт некорректный!')])

    email = EmailField('Емайл', render_kw={"placeholder": "info@romashka.ru"},
                       validators=[validators.Email()])


class FormContact(Form):
    tel = IntegerField('Телефон *',
                       render_kw={"placeholder":
                                  "Например, 74957775522. Без пробелов",
                                  "pattern": "[\+]?[0-9]{11,12}"},
                       validators=[DataRequired()])

    contact_person = StringField('Контактное лицо',
                                 render_kw={"placeholder": "ФИО"})

    post = StringField('Должность', render_kw={"placeholder":
                                                        "Например, директор"})


class FormClientCardAdd(FormClientCard, FormContact):  # Наследование класса
    comments = TextAreaField('Комментарий о компании', render_kw={'rows': 5})
    submit = SubmitField('Создать нового клиента')


class FormClientCardEdit(FormClientCard):
    client_id = HiddenField("client_id")

    nextcall = get_datetime('Дата следующего звонка', "datetimepicker2")

    comments = TextAreaField('Комментарий о компании', render_kw={'rows': 5})

    submit = SubmitField('Сохранить')

    saveandgo = SubmitField('Сохранить и перейти на главную')


class FormEvent(Form):
    title = StringField('Запланированное событие', render_kw={
        "placeholder": 'Например, выставить счет'}, validators=[DataRequired()])

    color = SelectField('Цвет события в календаре', choices=[
        ('#337ab7', 'Темно-синий'), ('#40E0D0', 'Бирюзовый'),
        ('#008000', 'Зеленый'), ('#FFD700', 'Желтый'),
        ('#FF8C00', 'Оранжевый'), ('#FF0000', 'Красный'), ('#000', 'Черный')])

    start = get_datetime('Время начала события', 'start')

    end = get_datetime('Время завершения события', 'end')


class FormEventAdd(FormEvent):
    submit = SubmitField('Создать новое событие в календаре')


class FormEventUpdate(FormEvent):
    id = HiddenField("id")
    submit = SubmitField('Изменить событие')
    delete = SubmitField('Удалить событие')


class FormCallReminde(Form):
    id = HiddenField("id")
    client_id = HiddenField("client_id")
    call_date = get_datetime('Дата и время следующего звонка', 'call_date')
    submit = SubmitField('Сохранить')


class FormAddUser(Form):
    login = StringField(
        'Логин', render_kw={
            "pattern": "[a-zA-Z0-9-]+",
            "placeholder": 'Для логина подходят цифры или латинские буквы'},
        validators=[DataRequired()])
    passw = StringField('Пароль', validators=[DataRequired()])
    name = StringField('Имя', render_kw={"placeholder": "Например, Иван Котов"})


class FormAddRuk(FormAddUser):
    submit = SubmitField('Сохранить')


class FormAddManager(FormAddUser):
    exten = IntegerField(
        'Внутренний номер',
        render_kw={"placeholder": "Внутренний номер сотрудника от 100 до 899",
                   "pattern": "[\+]?[0-9]{3,3}", "min": "100", "max": "899",
                   "type": "number"}, validators=[DataRequired()])

    prefix = SelectField('Префикс, для Москвы и Питера', choices=[
        ('9', '9 - Москва'), ('07', '07 - Питер')])
    ruk_id = SelectField('Руководитель', validators=[DataRequired()])
    submit = SubmitField('Сохранить')
