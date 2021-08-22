from flask import Flask, render_template, g, session, request, redirect, \
    url_for, flash
import os.path
from flask_bootstrap import Bootstrap
from forms import FormClientCardAdd, FormClientCardEdit, FormEventAdd, \
    FormEventUpdate, FormCallReminde, FormAddRuk, FormAddManager, FormContact
from logging.handlers import RotatingFileHandler
from logging import Formatter
import logging
import time
import csv
from sqlalchemy.sql.expression import func
from sqlalchemy.sql import text
# from sqlalchemy import exc
# from htmlmin.minify import html_minify  # Сжатие html
from datetime import timedelta
from flask_seasurf import SeaSurf
from flask_caching import Cache  # Автоматом добавляет к ключу префикс _flask
from models import db, Client, CallRemind, Contact, CallHistory, Event, User, \
    AuthLog
from datetime import datetime
import aster
import json

app = Flask(__name__)

# -----------------------------------------------------------------------------
# config.DevelopmentConfig или config.ProductionConfig
# -----------------------------------------------------------------------------

app.config.from_object('config.ProductionConfig')
app.jinja_env.trim_blocks = True  # Очищает пустые строки
app.jinja_env.lstrip_blocks = True  # Очищает пробелы
app.jinja_env.add_extension('jinja2.ext.loopcontrols')  # range, continue в тпл
db.init_app(app)
bootstrap = Bootstrap(app)
app.permanent_session_lifetime = timedelta(days=3650)
csrf = SeaSurf(app)
NUM_PER_PAGE = 10  # Кол-во записей на странице при пагинации
cache = Cache(app, config={'CACHE_TYPE': 'memcached',
                           "CACHE_MEMCACHED_SERVERS": ['127.0.0.1:11211']})
# -----------------------------------------------------------------------------
# Включение, отключение и ротация логов.
# -----------------------------------------------------------------------------

handler = RotatingFileHandler(app.config['LOGFILE'],
                              maxBytes=1000000, backupCount=1)
handler.setLevel(logging.DEBUG)
handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s '
                               '[in %(pathname)s:%(lineno)d]'))
# logging.disable(logging.CRITICAL)  # Расскоментарь это для прекращения логов
app.logger.addHandler(handler)


# -----------------------------------------------------------------------------
# Хуки и Функции
# -----------------------------------------------------------------------------


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.before_request
def before_request():
    g.date_today = time.strftime('%Y%m%d')
    session.permanent = True
    g.user_id = session.get('user_name', None)
    g.role = session.get('role', None)
    g.start = time.time()
    if ('user_name' not in session and request.endpoint != 'login'
            and not request.path.startswith('/static/')):
        return redirect(url_for('login'))

    if g.user_id:
        if not g.user_id.isdigit() and '/crm/' in request.path:
            flash('CRM только для менеджеров!', 'danger')
            return redirect(request.referrer)  # Возвращаем  откуда он пришел
        if g.role != 'boss' and '/boss/' in request.path:
            return redirect(request.referrer)


@app.after_request
def add_header(response):
    """Запрещаяем всяческое кеширование из-за IE и json и модальных окон"""
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


@app.teardown_request
def teardown_request(exception=None):
    diff = time.time() - g.start
    if '_ajax' not in request.path:
        app.logger.debug('Время загрузки: %s => %s', request.path, diff)


def row2dict(row):  # Из того, что приходит из базы делает словарь
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))
    return d


def delete_callremind(_id_):
    key = 'CallRemind:' + g.user_id
    cache.set(key, None)
    CR = CallRemind
    CR.query.filter(CR.user_id == g.user_id, CR.id == _id_).delete()
    db.session.commit()
    return True


def add_to_Contact(client_id, user_id, tel, contact_person, post):  # в Contact
    contact_insert = Contact(client_id, user_id, tel, contact_person, post)
    db.session.add(contact_insert)
    db.session.commit()


def update_Contact(contact_id, user_id, tel, contact_person, post):
    Co = Contact
    Co.query.filter(Co.id == contact_id, Co.user_id == user_id).update({
        'tel': tel, 'contact_person': contact_person, 'post': post})
    db.session.commit()


def date_handler(obj):  # Исправляет ошибку при рендеринге в json и датой
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


def add_or_update_call_reminde(nextcall, client_id):  # Вст./изм. время сл. звон
    call_date = datetime.strptime(nextcall, '%d.%m.%Y %H:%M')
    CR = CallRemind
    client = CR.query.filter_by(user_id=g.user_id, client_id=client_id).first()
    if client:
        CR.query.filter_by(client_id=client_id).update({'call_date': call_date})
    else:
        me = CR(g.user_id, call_date,  client_id)
        db.session.add(me)

    db.session.commit()
    return True


# -----------------------------------------------------------------------------
#  Роуты общие для всех
# -----------------------------------------------------------------------------


@csrf.include
@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():  # Авторизация
    if request.method == 'POST':
        f = request.form
        row = User.query.filter_by(login=f['usern'], passw=f['passw']).first()
        if row:

            me = AuthLog(row.login)  # Пишем в базу время входа юзера
            db.session.add(me)
            db.session.commit()

            session['role'] = row.role
            if row.role == 'boss':
                session['user_name'] = row.login
                return redirect(url_for('area_boss_index'))
            if row.role == 'ruk':
                session['user_name'] = row.login
                return redirect(url_for('area'))
            if row.role == 'manager':
                session['user_name'] = str(row.exten)
                return redirect(url_for('area_crm'))
        else:
            return redirect(url_for('login'))
    return render_template("login.html")


@app.route('/logout/')
def logout():
    session.pop('user_name', None)
    session.pop('role', None)
    return redirect(url_for('login'))


@app.route('/area/', defaults={'date': 0})
@app.route('/area/<int:date>/')
def area(date):
    if not date:
        date = g.date_today

    # Из csv файлов за каждый день берем продолжительность
    csv_patch = '/home/w2/thewire/media/mp3/' + str(date) + '.csv'
    length_dict = {}
    unix_hash = {}
    if os.path.isfile(csv_patch):
        with open(csv_patch) as f:
            length_dict = dict(filter(None, csv.reader(f)))
            for f in length_dict:
                arr = f.split('-')
                # app.logger.warning(arr)

                # Ограничение для обычных юзеров
                if g.user_id.isdigit() and g.user_id not in arr:
                    continue

                # Ограничение для смотрящими за серией
                if g.user_id.endswith('xx'):
                    start_dig = g.user_id[0]
                    if (not arr[1].startswith(start_dig)
                            and not arr[2].startswith(start_dig)):
                        continue

                # Ограничение для юзера прослушивания юзера 500 от админа
                if g.user_id != 'boss' and '500' in arr:
                    continue

                unix_hash[arr[4]] = [f] + arr

    # Разрешаем юзать jquery фильтр для админов и смотрящих
    admin_filter = False
    if not g.user_id.isdigit():
        admin_filter = True

    return render_template("area.html", unix_hash=unix_hash, date=str(date),
                           length_dict=length_dict, admin_filter=admin_filter)


@app.route('/newdate/', methods=['POST'])
def newdate():
    date = request.form['date_sf']
    date = datetime.strptime(date, '%d.%m.%Y').strftime('%Y%m%d')
    if not date:
        return 'Выберите дату. <a href="javascript: history.go(-1)">Назад</a>'
    return redirect(url_for('area', date=date))


@app.route('/area/crm/')
def area_crm():
    return render_template("crm_index.html")

@app.route('/kanban')
def kanban_crm():
    return render_template("kanban_index.html")

@app.route('/area/crm/add/new/client/', methods=['GET', 'POST'])
def areacrm_add_new_client():  # Добавляем нового клиента
    form = FormClientCardAdd()
    if request.method == 'GET':
        return render_template("add_new_client.html", form=form)

    f = request.form
    me = Client(g.user_id, f['status'], f['city'], f['segment'],
                f['company_name'], f['site'], f['email'], f['comments'], None,
                None, f['loyalty'], f['activity'])
    db.session.add(me)
    db.session.commit()

    add_to_Contact(me.id, g.user_id, f['tel'], f['contact_person'], f['post'])

    flash('Клиент успешно добавлен', 'success')
    return redirect(url_for('area_crm'))


@app.route('/area/crm/edit/<int:client_id>/')
def area_crm_edit_and_call(client_id):  # Редактирование клиента
    rows = Client.query.filter_by(id=client_id, user_id=g.user_id).first()
    # Присваиваем формам значения из базы c помощью obj=rows и единичные поля
    # отдельно с помощью form.fild_name.data = какое-то значение
    form = FormClientCardEdit(obj=rows)
    form.client_id.data = client_id
    time = CallRemind.query.filter_by(client_id=client_id).first()
    if time:  # Присваиваем формам значения из базы
        form.nextcall.data = time.call_date
    contact = Contact.query.filter_by(client_id=client_id)
    return render_template("edit_client.html", rows=rows, time=time,
                           contact=contact, form=form)


@app.route('/area/crm/callhistory/<int:client_id>/', defaults={'page': 1})
@app.route('/area/crm/callhistory/<int:client_id>/<int:page>/')
def area_crm_callhistory(client_id, page):
    # Забираем join-ом из двух таблиц данные о клиенте
    Co = Contact
    Cl = Client
    client_info = db.session.query(Cl, Co).join(Co).filter(
        Cl.user_id == g.user_id, Cl.id == client_id)
    Ch = CallHistory
    r = Ch.query.filter_by(user_id=g.user_id, client_id=client_id).order_by(
        Ch.id.desc()).paginate(page, NUM_PER_PAGE, True)
    return render_template("crm_callhistory.html", client_info=client_info,
                           rows=r.items, pagination=r, iter_pages=r.iter_pages)


@app.route('/area/crm/init/call/<int:client_id>/<int:tel>/')
def area_crm_init_call(client_id, tel):  # Иницация звонка и редирект в историю
    _id_ = request.args.get('callremid')
    if _id_:
        delete_callremind(_id_)

    aster.run_call(g.user_id, tel)
    me = CallHistory(g.user_id, client_id, g.user_id, tel)
    db.session.add(me)
    db.session.commit()
    return redirect(url_for('area_crm_callhistory', client_id=client_id))


@app.route('/area/crm/edit/client/', methods=['POST'])
def area_crm_edit_client():  # Редактирование клиента POST
    f = request.form
    C = Client
    C.query.filter(C.id == f['client_id'], C.user_id == g.user_id).update(
        {'status': f['status'], 'city': f['city'], 'segment': f['segment'],
         'company_name': f['company_name'], 'site': f['site'],
         'email': f['email'], 'comments': f['comments'],
         'loyalty': f['loyalty'], 'activity': f['activity']})
    db.session.commit()

    if f['nextcall']:
        add_or_update_call_reminde(f['nextcall'], f['client_id'])

    flash('Изменения в карточку клиента записаны', 'success')
    if f.get('saveandgo'):
        return redirect(url_for('area_crm'))

    return redirect(url_for('area_crm_edit_and_call', client_id=f['client_id']))


@app.route('/area/crm/del/client/<int:client_id>/')
def area_crm_del_client(client_id):
    C = Client
    C.query.filter(C.user_id == g.user_id, C.id == client_id).delete()
    db.session.commit()
    CR = CallRemind
    CR.query.filter(CR.user_id == g.user_id, CR.client_id == client_id).delete()
    db.session.commit()
    flash('Клиент был успешно удален!', 'info')
    return redirect(url_for('area_crm'))


@app.route('/area/crm/del/callrem/<int:_id_>/')
def area_crm_del_callrem(_id_):  # Удаляем напоминание о звонке
    delete_callremind(_id_)
    flash('Звонок клиенту отменен', 'danger')
    return redirect(request.referrer)  # Возвращаем  откуда он пришел


@app.route('/area/crm/records/<client_id>/')
def area_crm_records(client_id):  # Записи разговоров с клиентом
    C = Client
    r = C.query.filter_by(user_id=g.user_id, id=client_id).first()
    r = row2dict(r)
    patch = '/home/w2/thewire/media/mp3/'
    records = {}
    phones = Contact.query.filter_by(user_id=g.user_id,
                                     client_id=client_id).all()
    for p in phones:
        client_tel = str(p.tel)
        for f in os.listdir(patch):
            if client_tel in f:
                arr = f.split('-')
                posix_time = arr[5].split('.')
                call_date = datetime.fromtimestamp(
                    int(posix_time[0])).strftime('%d.%m.%Y %H:%M:%S')
                records[call_date] = f

    return render_template("area_crm_records.html", records=records, r=r)


@app.route('/area/help/')
def area_help():
    return render_template("area_help.html")


@app.route('/area/crm/fullcalendar/modal/<action>/')
def area_crm_fullcalendar_modal(action):  # Модальное окно большого календаря
    r = request.args

    if action == 'insert':
        form = FormEventAdd()
        start = datetime.strptime(r.get('start_event'), '%Y-%m-%d %H:%M')
        end = datetime.strptime(r.get('end_event'), '%Y-%m-%d %H:%M')
        form.start.data = start
        form.end.data = end

    if action == 'update':
        _id_ = r.get('id')
        E = Event
        row = E.query.filter_by(user_id=g.user_id, id=_id_).first_or_404()
        form = FormEventUpdate(obj=row)

    return render_template("modal_full_calendar.html", form=form, action=action)


@app.route('/area/crm/fullcalendar/insert/', methods=['POST'])
def area_crm_fullcalendar_add():  # Вставляем новые события календаря в базу
    f = request.form
    start = datetime.strptime(f['start'], '%d.%m.%Y %H:%M')
    end = datetime.strptime(f['end'], '%d.%m.%Y %H:%M')
    me = Event(g.user_id, start, end, f['title'], f['color'])
    db.session.add(me)
    db.session.commit()

    flash('Событие успешно добавлено', 'success')
    return redirect(url_for('area_crm'))


@app.route('/area/crm/fullcalendar/update/', methods=['POST'])
def area_crm_fullcalendar_update():  # Изм. событие календаря в базе
    f = request.form
    start = datetime.strptime(f['start'], '%d.%m.%Y %H:%M')
    end = datetime.strptime(f['end'], '%d.%m.%Y %H:%M')
    E = Event
    flash_text = flash_status = ""
    if f.get('delete'):
        E.query.filter_by(user_id=g.user_id, id=f['id']).delete()
        flash_text = "Событие удалено"
        flash_status = "warning"
    else:
        E.query.filter_by(id=f['id'], user_id=g.user_id).update({
            'start': start, 'end': end, 'title': f['title'],
            'color': f['color']})
        flash_text = "Событие было изменено"
        flash_status = "success"
    db.session.commit()
    flash(flash_text, flash_status)
    return redirect(url_for('area_crm'))


@app.route('/area/crm/set-call-reminde/modal/')
def area_crm_set_call_reminde_modal():  # В модальном меняем дату след. звонка
    form = FormCallReminde()
    client_id = request.args.get('client_id')
    row = CallRemind.query.filter_by(user_id=g.user_id,
                                     client_id=client_id).first()
    if row:
        form = FormCallReminde(obj=row)
    else:
        form.client_id.data = client_id
    return render_template("modal_set_call_reminde.html", form=form)


@app.route('/area/crm/set-call-reminde/', methods=['POST'])
def area_crm_set_call_reminde():  # Меняем/устанавливаем дату след. звонка POST
    f = request.form
    add_or_update_call_reminde(f['call_date'], f['client_id'])
    flash("Напоминание о запланированном звонке сохранено.", "success")
    return redirect(request.referrer)  # Возвращаем  откуда он пришел


@app.route('/area/crm/show/modal/site/email/')
def area_crm_show_modal_site_email():  # В модальном окне показ. сайт и мыло
    client_id = request.args.get('client_id')
    Cl = Client
    Co = Contact
    info = db.session.query(Cl, Co).join(Co).filter(
        Cl.user_id == g.user_id, Cl.id == client_id).all()
    return render_template("modal_show_site_email.html", info=info)


@app.route('/area/crm/today/plan/call/')
def area_crm_today_plan_call():  # План звонков на сегодня
    sql = text(
        """
        SELECT
        a.id,
        a.status,
        a.city,
        a.site,
        a.segment,
        a.company_name,
        a.site,
        a.email,
        a.comments,
        b.id as call_remind_id,
        b.call_date,
        c.tel,
        c.contact_person,
        (select comment from call_history where client_id = a.id order by
        id desc limit 0,1) as hist_comment,
        a.loyalty
        FROM clients a
        INNER JOIN call_remind b ON a.id = b.client_id
        INNER JOIN contacts c ON a.id = c.client_id
        WHERE a.user_id = :user_id AND Date(b.call_date) = CURDATE()
        ORDER BY b.call_date
        """)
    raw = db.session.execute(sql, {'user_id': g.user_id}).fetchall()
    rows = [dict(r) for r in raw]

    return render_template("today_plan_call.html", rows=rows)


@app.route('/area/crm/modal/add/contact/')
def area_crm_modal_add_contact():  # В модальном окне доб. контакт
    client_id = request.args.get('client_id')
    form = FormContact()
    return render_template("modal_add_contact.html", client_id=client_id,
                           form=form)


@app.route('/area/crm/add/new/contact/', methods=['POST'])
def area_crm_add_new_contact():  # Вставляем в базу контакты POST
    f = request.form
    add_to_Contact(f['client_id'], g.user_id, f['tel'], f['contact_person'],
                   f['post'])
    flash('Контактное лицо успешно добавлено!', 'success')
    return redirect(request.referrer)  # Возвращаем  откуда он пришел


@app.route('/area/crm/modal/edit/contact/')
def area_crm_modal_edit_contact():  # В модальном окне редактир. контакт
    client_id = request.args.get('client_id')
    contact_id = request.args.get('contact_id')
    contact = Contact.query.filter_by(id=contact_id).first()
    form = FormContact(obj=contact)
    return render_template("modal_edit_contact.html", client_id=client_id,
                           contact_id=contact_id, form=form)


@app.route('/area/crm/edit/contact/', methods=['POST'])
def area_crm_edit_contact():  # Редактируем контакт, POST
    f = request.form
    update_Contact(f['contact_id'], g.user_id, f['tel'],
                   f['contact_person'], f['post'])
    flash('Контактное лицо успешно изменено!', 'success')
    return redirect(request.referrer)  # Возвращаем  откуда он пришел


# -----------------------------------------------------------------------------
# Роуты Boss
# -----------------------------------------------------------------------------

@app.route('/area/boss/index/')
def area_boss_index():  # Главная страница босса
    rows = User.query.order_by(User.login).all()
    return render_template('boss_index.html', rows=rows)


@app.route('/area/boss/add/new/ruk/', methods=['GET', 'POST'])
def area_boss_add_new_ruk():  # Добавление нового рука
    form = FormAddRuk()
    if request.method == 'POST' and form.validate_on_submit():
        if User.check_exist(form.login.data, None):
            flash('Ошибка! Юзер с таким логином уже существует!', 'danger')
        else:
            me = User(form.login.data, form.passw.data, None, None, 'ruk', None,
                      form.name.data)
            db.session.add(me)
            db.session.commit()
            flash('Руководитель успешно создан!', 'success')
            return redirect(url_for('area_boss_index'))

    return render_template('boss_add_ruk.html', form=form)


@app.route('/area/boss/add/new/manager/', methods=['GET', 'POST'])
def area_boss_add_new_manager():  # Добавление нового менеджера
    form = FormAddManager()
    # Динамически формируем список руков из базы
    form.ruk_id.choices = [(str(a.id), a.login) for a in User.query.filter_by(
        role='ruk').order_by(User.login).all()]
    form.ruk_id.choices.insert(0, ("", "Выберите руководителя"))

    if request.method == 'POST' and form.validate_on_submit():
        if User.check_exist(form.login.data, form.exten.data):
            flash('Ошибка! Такой логин или внтр. номер существует!', 'danger')
        else:
            me = User(form.login.data, form.passw.data, form.exten.data,
                      form.prefix.data, 'manager', form.ruk_id.data,
                      form.name.data)
            db.session.add(me)
            db.session.commit()
            flash('Менеджер успешно создан!', 'success')
            return redirect(url_for('area_boss_index'))

    return render_template('boss_add_manager.html', form=form)


@app.route('/area/boss/del/user/<int:_id_>/')
def area_boss_del_user(_id_):  # Удаление любых типов юзеров
    User.query.filter(User.id == _id_).delete()
    db.session.commit()
    flash('Юзер успешно удален!', 'info')
    return redirect(url_for('area_boss_index'))


@app.route('/area/boss/edit/ruk/<int:_id_>/', methods=['GET', 'POST'])
def area_boss_edit_ruk(_id_):  # В модальном окне редактируем менеджера
    form = FormAddRuk()
    if request.method == 'POST' and form.validate_on_submit():
        User.query.filter_by(id=_id_).update(
            {'passw': form.passw.data, 'name': form.name.data})
        db.session.commit()
        flash('Изменения приняты!', 'success')
        return redirect(url_for('area_boss_index'))

    obj = User.query.filter_by(id=_id_).first()
    form = FormAddRuk(obj=obj)
    return render_template("boss_edit_ruk.html", form=form, _id_=str(_id_))


@app.route('/area/boss/edit/manager/<int:_id_>/', methods=['GET', 'POST'])
def area_boss_edit_manager(_id_):  # В модальном окне редактируем менеджера
    if request.method == 'POST':
        f = request.form
        User.query.filter_by(id=_id_).update({'passw': f['passw'],
                                              'name': f['name'],
                                              'prefix': f['prefix'],
                                              'ruk_id': f['ruk_id']})
        db.session.commit()
        flash('Изменения приняты!', 'success')
        return redirect(url_for('area_boss_index'))

    obj = User.query.filter_by(id=_id_).first()
    form = FormAddManager(obj=obj)
    # Динамически формируем список менеджеров из базы
    form.ruk_id.choices = [(str(a.id), a.login) for a in User.query.filter_by(
        role='ruk').order_by(User.login).all()]
    form.ruk_id.choices.insert(0, ("", "Выберите руководителя"))
    return render_template("boss_edit_manager.html", form=form, _id_=str(_id_))


# -----------------------------------------------------------------------------
# Ajax роуты
# -----------------------------------------------------------------------------


@app.route('/area/crm/CallRemind/_ajax')
def area_crm_CallRemind_ajax():  # Запросы о запланированных звонках
    data = {}
    CR = CallRemind
    # Кешируем запрос на 10 секунд
    key = 'CallRemind:' + g.user_id
    plan = cache.get(key)
    if not plan:
        plan = CR.query.filter(CR.user_id == g.user_id, CR.status == 0,
                               CR.call_date <= datetime.now()).order_by(
                                   CR.call_date).first()
        cache.set(key, plan, timeout=10)

    if plan:
        plan = row2dict(plan)
        c = Client.query.filter_by(id=plan['client_id']).first()
        date = datetime.strptime(plan['call_date'],
                                 '%Y-%m-%d %H:%M:%S').strftime(
                                     '%d.%m.%Y %H:%M:%S')
        phones = Contact.query.with_entities(
            Contact.tel, Contact.contact_person).filter_by(
                client_id=plan['client_id']).all()
        plan['call_date'] = date
        data['client'] = row2dict(c)
        data['call_remind'] = plan
        data['phones'] = phones

    return json.dumps(data)


@app.route('/area/crm/autosave/comment/_ajax', methods=['POST'])
def area_crm_autosave_comment_ajax():  # Автоматическое сохранение комментов
    f = request.form
    C = CallHistory
    C.query.filter(C.id == f['id'], C.user_id == g.user_id).update(
        {'comment': f['comment']})
    db.session.commit()
    return "1"


@app.route('/area/crm/get/incomming/call/_ajax')
def area_crm_get_incomming_call_ajax():  # Отлавливаем входящие звонки
    key = 'incall:' + g.user_id
    struct = cache.get(key)  # Автоматом добавляет к ключу префикс _flask
    if struct:
        return struct
    else:
        return "{}"


@app.route('/area/crm/get/incomming/call/del/_ajax')
def area_crm_get_incomming_call_del_ajax():  # Удаляем сообщ. о вх. звонке
    key = 'incall:' + g.user_id
    cache.set(key, "{}")
    return "{}"


@app.route('/area/crm/updateEvent/_ajax', methods=['POST'])
def area_crm_updateEvent_ajax():  # Изм. время события с помощью перемещения
    f = request.form
    start = datetime.strptime(f.get('start'), '%Y-%m-%d %H:%M')
    end = datetime.strptime(f.get('end'), '%Y-%m-%d %H:%M')
    E = Event
    E.query.filter_by(id=f['id'], user_id=g.user_id).update({
        'start': start, 'end': end})
    db.session.commit()
    return 'OK'


@app.route('/area/crm/fullcalendar/get/events/_ajax')
def area_crm_fullcalendar_get_events_ajax():  # Все события в календаре
    E = Event
    rows = E.query.filter_by(user_id=g.user_id
                             ).order_by(E.id.desc()).limit(500).all()
    arr = []
    for row in rows:
        arr.append(row2dict(row))
    return json.dumps(arr)


@app.route('/area/crm/get/all/clients/ajax/new/')
def area_crm_get_all_clients_ajax_new():  # Для datatable выдаем ajax ответ
    # Формируем словарь с датой последнего звонка клиенту или от клиента
    Ch = CallHistory
    call_hist = \
        Ch.query.with_entities(Ch.client_id, func.max(Ch.date_call)).filter_by(
            user_id=g.user_id).group_by(Ch.client_id)
    call_hist_dic = {r[0]: r[1] for r in call_hist}

    # Формируем словарь с датой запланированного звонка
    Cr = CallRemind
    call_reminde = Cr.query.with_entities(
        Cr.client_id, Cr.call_date).filter_by(user_id=g.user_id)
    call_dic = {r[0]: r[1] for r in call_reminde}

    # Формируем таблицу с клиентами и телефонами
    Cl = Client
    Co = Contact
    raw = db.session.query(Cl, Co).join(Co).filter(Cl.user_id == g.user_id)

    arr = []
    tmp_dic = {}

    for index, r in enumerate(raw):
        C = r.Client
        P = r.Contact
        if tmp_dic.get(C.id):
            arr[-1][8].append(P.tel)  # Если телефонов несколько
        else:
            # После C.activity, "" передается пустая запись, можно чем-нибудь
            # заменить
            C.city = C.city.upper() if C.city else ""
            C.company_name = C.company_name.replace('"', "'")
            last_call = call_hist_dic.get(C.id, None)
            call_remind = call_dic.get(C.id, None)
            arr.extend([[C.status, C.city, C.segment,
                         C.company_name, C.activity, "", last_call,
                         call_remind, [P.tel], C.id, C.loyalty]])
            tmp_dic[C.id] = 1
    # indent=4 * ' ' # Добавь, если нужно форматирование
    return json.dumps({"data": arr}, ensure_ascii=False, default=date_handler)


@app.route('/area/crm/check/uniq/tel/_ajax')
def area_crm_check_uniq_tel_ajax():  # Проверка телефона на уникальность
    tel = request.args.get('tel')
    result = Contact.check_uniq(tel)
    if result:
        return "Not uniq"
    else:
        return "Uniq"


if __name__ == "__main__":
        # app.debug = True
        app.run(host='0.0.0.0')
