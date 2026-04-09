#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

import json
from datetime import datetime
import dateutil.parser
import babel
from flask import Flask, render_template, request, Response, flash, redirect, url_for
from flask_migrate import Migrate
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
import logging
from logging import Formatter, FileHandler
from sqlalchemy import case, func
from sqlalchemy.orm import contains_eager, joinedload
from forms import *
#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
db = SQLAlchemy(app)

# TODO: connect to a local postgresql database
migrate = Migrate(app, db)

#----------------------------------------------------------------------------#
# Models.
#----------------------------------------------------------------------------#

venue_genres = db.Table(
    'venue_genres',
    db.Column('venue_id', db.Integer, db.ForeignKey('Venue.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('Genre.id', ondelete='CASCADE'), primary_key=True),
)

artist_genres = db.Table(
    'artist_genres',
    db.Column('artist_id', db.Integer, db.ForeignKey('Artist.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('Genre.id', ondelete='CASCADE'), primary_key=True),
)


class Genre(db.Model):
    __tablename__ = 'Genre'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

class Venue(db.Model):
    __tablename__ = 'Venue'
    __table_args__ = (
        db.UniqueConstraint('name', 'city', 'state', 'address', name='uq_venue_identity'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(120))
    image_link = db.Column(db.String(500))
    facebook_link = db.Column(db.String(500))
    website = db.Column(db.String(500))
    seeking_talent = db.Column(db.Boolean, nullable=False, default=False)
    seeking_description = db.Column(db.String(500))
    genres = db.relationship('Genre', secondary=venue_genres, lazy='selectin')
    shows = db.relationship('Show', back_populates='venue', cascade='all, delete-orphan', lazy=True)

    # TODO: implement any missing fields, as a database migration using Flask-Migrate

class Artist(db.Model):
    __tablename__ = 'Artist'
    __table_args__ = (
        db.UniqueConstraint('name', 'city', 'state', 'phone', name='uq_artist_identity'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(120))
    image_link = db.Column(db.String(500))
    facebook_link = db.Column(db.String(500))
    website = db.Column(db.String(500))
    seeking_venue = db.Column(db.Boolean, nullable=False, default=False)
    seeking_description = db.Column(db.String(500))
    genres = db.relationship('Genre', secondary=artist_genres, lazy='selectin')
    shows = db.relationship('Show', back_populates='artist', cascade='all, delete-orphan', lazy=True)

    # TODO: implement any missing fields, as a database migration using Flask-Migrate

# TODO Implement Show and Artist models, and complete all model relationships and properties, as a database migration.
class Show(db.Model):
    __tablename__ = 'Show'
    __table_args__ = (
        db.UniqueConstraint('artist_id', 'venue_id', 'start_time', name='uq_show_listing'),
    )

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey('Artist.id', ondelete='CASCADE'), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('Venue.id', ondelete='CASCADE'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    artist = db.relationship('Artist', back_populates='shows')
    venue = db.relationship('Venue', back_populates='shows')

#----------------------------------------------------------------------------#
# Filters.
#----------------------------------------------------------------------------#

def format_datetime(value, format='medium'):
  date = value if isinstance(value, datetime) else dateutil.parser.parse(value)
  if format == 'full':
      format="EEEE MMMM, d, y 'at' h:mma"
  elif format == 'medium':
      format="EE MM, dd, y h:mma"
  return babel.dates.format_datetime(date, format, locale='en')

app.jinja_env.filters['datetime'] = format_datetime


def current_time():
  return datetime.now()


def genre_names(entity):
  return [genre.name for genre in entity.genres]


def get_or_create_genres(names):
  genre_values = sorted(set(names or []))
  if not genre_values:
    return []

  existing_genres = Genre.query.filter(Genre.name.in_(genre_values)).all()
  genres_by_name = {genre.name: genre for genre in existing_genres}

  for name in genre_values:
    if name not in genres_by_name:
      genre = Genre(name=name)
      db.session.add(genre)
      genres_by_name[name] = genre

  return [genres_by_name[name] for name in genre_values]


def build_upcoming_show_count_expression():
  return func.sum(
    case(
      (Show.start_time > current_time(), 1),
      else_=0,
    )
  ).label('num_upcoming_shows')


def serialize_show_for_venue(show):
  return {
    'artist_id': show.artist.id,
    'artist_name': show.artist.name,
    'artist_image_link': show.artist.image_link,
    'start_time': show.start_time,
  }


def serialize_show_for_artist(show):
  return {
    'venue_id': show.venue.id,
    'venue_name': show.venue.name,
    'venue_image_link': show.venue.image_link,
    'start_time': show.start_time,
  }


def split_venue_shows(shows):
  past_shows = []
  upcoming_shows = []
  now = current_time()

  for show in sorted(shows, key=lambda show: show.start_time):
    serialized_show = serialize_show_for_venue(show)
    if show.start_time > now:
      upcoming_shows.append(serialized_show)
    else:
      past_shows.append(serialized_show)

  return past_shows, upcoming_shows


def split_artist_shows(shows):
  past_shows = []
  upcoming_shows = []
  now = current_time()

  for show in sorted(shows, key=lambda show: show.start_time):
    serialized_show = serialize_show_for_artist(show)
    if show.start_time > now:
      upcoming_shows.append(serialized_show)
    else:
      past_shows.append(serialized_show)

  return past_shows, upcoming_shows


def populate_venue_from_form(venue, form):
  venue.name = form.name.data
  venue.city = form.city.data
  venue.state = form.state.data
  venue.address = form.address.data
  venue.phone = form.phone.data
  venue.genres = get_or_create_genres(form.genres.data)
  venue.image_link = form.image_link.data
  venue.facebook_link = form.facebook_link.data
  venue.website = form.website_link.data
  venue.seeking_talent = form.seeking_talent.data
  venue.seeking_description = form.seeking_description.data


def populate_artist_from_form(artist, form):
  artist.name = form.name.data
  artist.city = form.city.data
  artist.state = form.state.data
  artist.phone = form.phone.data
  artist.genres = get_or_create_genres(form.genres.data)
  artist.image_link = form.image_link.data
  artist.facebook_link = form.facebook_link.data
  artist.website = form.website_link.data
  artist.seeking_venue = form.seeking_venue.data
  artist.seeking_description = form.seeking_description.data


def populate_artist_form(form, artist):
  form.name.data = artist.name
  form.city.data = artist.city
  form.state.data = artist.state
  form.phone.data = artist.phone
  form.genres.data = genre_names(artist)
  form.facebook_link.data = artist.facebook_link
  form.image_link.data = artist.image_link
  form.website_link.data = artist.website
  form.seeking_venue.data = artist.seeking_venue
  form.seeking_description.data = artist.seeking_description


def populate_venue_form(form, venue):
  form.name.data = venue.name
  form.city.data = venue.city
  form.state.data = venue.state
  form.address.data = venue.address
  form.phone.data = venue.phone
  form.genres.data = genre_names(venue)
  form.facebook_link.data = venue.facebook_link
  form.image_link.data = venue.image_link
  form.website_link.data = venue.website
  form.seeking_talent.data = venue.seeking_talent
  form.seeking_description.data = venue.seeking_description

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
  return render_template('pages/home.html')


#  Venues
#  ----------------------------------------------------------------

@app.route('/venues')
def venues():
  # TODO: replace with real venues data.
  #       num_upcoming_shows should be aggregated based on number of upcoming shows per venue.
  upcoming_show_count = build_upcoming_show_count_expression()
  venue_rows = (
    db.session.query(
      Venue.id,
      Venue.name,
      Venue.city,
      Venue.state,
      upcoming_show_count,
    )
    .outerjoin(Show, Show.venue_id == Venue.id)
    .group_by(Venue.id)
    .order_by(Venue.state, Venue.city, Venue.name)
    .all()
  )

  grouped_venues = {}
  for venue in venue_rows:
    key = (venue.city, venue.state)
    if key not in grouped_venues:
      grouped_venues[key] = {
        'city': venue.city,
        'state': venue.state,
        'venues': [],
      }
    grouped_venues[key]['venues'].append({
      'id': venue.id,
      'name': venue.name,
      'num_upcoming_shows': int(venue.num_upcoming_shows or 0),
    })

  data = list(grouped_venues.values())
  return render_template('pages/venues.html', areas=data);

@app.route('/venues/search', methods=['POST'])
def search_venues():
  # TODO: implement search on artists with partial string search. Ensure it is case-insensitive.
  # seach for Hop should return "The Musical Hop".
  # search for "Music" should return "The Musical Hop" and "Park Square Live Music & Coffee"
  upcoming_show_count = build_upcoming_show_count_expression()
  search_term = request.form.get('search_term', '').strip()
  matching_venues = (
    db.session.query(
      Venue.id,
      Venue.name,
      upcoming_show_count,
    )
    .outerjoin(Show, Show.venue_id == Venue.id)
    .filter(Venue.name.ilike(f'%{search_term}%'))
    .group_by(Venue.id)
    .order_by(Venue.name)
    .all()
  )
  response={
    "count": len(matching_venues),
    "data": [{
      "id": venue.id,
      "name": venue.name,
      "num_upcoming_shows": int(venue.num_upcoming_shows or 0),
    } for venue in matching_venues]
  }
  return render_template('pages/search_venues.html', results=response, search_term=search_term)

@app.route('/venues/<int:venue_id>')
def show_venue(venue_id):
  # shows the venue page with the given venue_id
  # TODO: replace with real venue data from the venues table, using venue_id
  venue = Venue.query.options(joinedload(Venue.genres)).get_or_404(venue_id)
  venue_shows = (
    db.session.query(Show)
    .join(Artist, Artist.id == Show.artist_id)
    .options(contains_eager(Show.artist))
    .filter(Show.venue_id == venue_id)
    .order_by(Show.start_time)
    .all()
  )
  past_shows, upcoming_shows = split_venue_shows(venue_shows)
  data = {
    'id': venue.id,
    'name': venue.name,
    'genres': genre_names(venue),
    'address': venue.address,
    'city': venue.city,
    'state': venue.state,
    'phone': venue.phone,
    'website': venue.website,
    'facebook_link': venue.facebook_link,
    'seeking_talent': venue.seeking_talent,
    'seeking_description': venue.seeking_description,
    'image_link': venue.image_link,
    'past_shows': past_shows,
    'upcoming_shows': upcoming_shows,
    'past_shows_count': len(past_shows),
    'upcoming_shows_count': len(upcoming_shows),
  }
  return render_template('pages/show_venue.html', venue=data)

#  Create Venue
#  ----------------------------------------------------------------

@app.route('/venues/create', methods=['GET'])
def create_venue_form():
  form = VenueForm()
  return render_template('forms/new_venue.html', form=form)

@app.route('/venues/create', methods=['POST'])
def create_venue_submission():
  # TODO: insert form data as a new Venue record in the db, instead
  # TODO: modify data to be the data object returned from db insertion
  form = VenueForm(request.form)
  data = None

  if not form.validate():
    flash('An error occurred. Venue ' + request.form.get('name', '') + ' could not be listed.')
    return render_template('forms/new_venue.html', form=form)

  try:
    data = Venue()
    populate_venue_from_form(data, form)
    db.session.add(data)
    db.session.commit()

  # on successful db insert, flash success
    flash('Venue ' + data.name + ' was successfully listed!')
  # TODO: on unsuccessful db insert, flash an error instead.
  # e.g., flash('An error occurred. Venue ' + data.name + ' could not be listed.')
  # see: http://flask.pocoo.org/docs/1.0/patterns/flashing/
  except Exception:
    db.session.rollback()
    flash('An error occurred. Venue ' + request.form.get('name', '') + ' could not be listed.')
  finally:
    db.session.close()

  return render_template('pages/home.html')

@app.route('/venues/<venue_id>', methods=['DELETE'])
def delete_venue(venue_id):
  # TODO: Complete this endpoint for taking a venue_id, and using
  # SQLAlchemy ORM to delete a record. Handle cases where the session commit could fail.
  data = Venue.query.get_or_404(int(venue_id))

  try:
    db.session.delete(data)
    db.session.commit()
  except Exception:
    db.session.rollback()
    return Response(status=500)
  finally:
    db.session.close()

  # BONUS CHALLENGE: Implement a button to delete a Venue on a Venue Page, have it so that
  # clicking that button delete it from the db then redirect the user to the homepage
  return Response(status=200)

#  Artists
#  ----------------------------------------------------------------
@app.route('/artists')
def artists():
  # TODO: replace with real data returned from querying the database
  data=[{
    "id": artist.id,
    "name": artist.name,
  } for artist in Artist.query.order_by(Artist.name).all()]
  return render_template('pages/artists.html', artists=data)

@app.route('/artists/search', methods=['POST'])
def search_artists():
  # TODO: implement search on artists with partial string search. Ensure it is case-insensitive.
  # seach for "A" should return "Guns N Petals", "Matt Quevado", and "The Wild Sax Band".
  # search for "band" should return "The Wild Sax Band".
  upcoming_show_count = build_upcoming_show_count_expression()
  search_term = request.form.get('search_term', '').strip()
  matching_artists = (
    db.session.query(
      Artist.id,
      Artist.name,
      upcoming_show_count,
    )
    .outerjoin(Show, Show.artist_id == Artist.id)
    .filter(Artist.name.ilike(f'%{search_term}%'))
    .group_by(Artist.id)
    .order_by(Artist.name)
    .all()
  )
  response={
    "count": len(matching_artists),
    "data": [{
      "id": artist.id,
      "name": artist.name,
      "num_upcoming_shows": int(artist.num_upcoming_shows or 0),
    } for artist in matching_artists]
  }
  return render_template('pages/search_artists.html', results=response, search_term=search_term)

@app.route('/artists/<int:artist_id>')
def show_artist(artist_id):
  # shows the artist page with the given artist_id
  # TODO: replace with real artist data from the artist table, using artist_id
  artist = Artist.query.options(joinedload(Artist.genres)).get_or_404(artist_id)
  artist_shows = (
    db.session.query(Show)
    .join(Venue, Venue.id == Show.venue_id)
    .options(contains_eager(Show.venue))
    .filter(Show.artist_id == artist_id)
    .order_by(Show.start_time)
    .all()
  )
  past_shows, upcoming_shows = split_artist_shows(artist_shows)
  data = {
    'id': artist.id,
    'name': artist.name,
    'genres': genre_names(artist),
    'city': artist.city,
    'state': artist.state,
    'phone': artist.phone,
    'website': artist.website,
    'facebook_link': artist.facebook_link,
    'seeking_venue': artist.seeking_venue,
    'seeking_description': artist.seeking_description,
    'image_link': artist.image_link,
    'past_shows': past_shows,
    'upcoming_shows': upcoming_shows,
    'past_shows_count': len(past_shows),
    'upcoming_shows_count': len(upcoming_shows),
  }
  return render_template('pages/show_artist.html', artist=data)

#  Update
#  ----------------------------------------------------------------
@app.route('/artists/<int:artist_id>/edit', methods=['GET'])
def edit_artist(artist_id):
  form = ArtistForm()
  artist = Artist.query.get_or_404(artist_id)
  # TODO: populate form with fields from artist with ID <artist_id>
  populate_artist_form(form, artist)
  return render_template('forms/edit_artist.html', form=form, artist=artist)

@app.route('/artists/<int:artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
  # TODO: take values from the form submitted, and update existing
  # artist record with ID <artist_id> using the new attributes
  form = ArtistForm(request.form)
  artist = Artist.query.get_or_404(artist_id)

  if not form.validate():
    flash('An error occurred. Artist ' + artist.name + ' could not be updated.')
    return render_template('forms/edit_artist.html', form=form, artist=artist)

  try:
    populate_artist_from_form(artist, form)
    db.session.commit()
  except Exception:
    db.session.rollback()
    flash('An error occurred. Artist ' + artist.name + ' could not be updated.')
    return render_template('forms/edit_artist.html', form=form, artist=artist)

  return redirect(url_for('show_artist', artist_id=artist_id))

@app.route('/venues/<int:venue_id>/edit', methods=['GET'])
def edit_venue(venue_id):
  form = VenueForm()
  venue = Venue.query.get_or_404(venue_id)
  # TODO: populate form with values from venue with ID <venue_id>
  populate_venue_form(form, venue)
  return render_template('forms/edit_venue.html', form=form, venue=venue)

@app.route('/venues/<int:venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
  # TODO: take values from the form submitted, and update existing
  # venue record with ID <venue_id> using the new attributes
  form = VenueForm(request.form)
  venue = Venue.query.get_or_404(venue_id)

  if not form.validate():
    flash('An error occurred. Venue ' + venue.name + ' could not be updated.')
    return render_template('forms/edit_venue.html', form=form, venue=venue)

  try:
    populate_venue_from_form(venue, form)
    db.session.commit()
  except Exception:
    db.session.rollback()
    flash('An error occurred. Venue ' + venue.name + ' could not be updated.')
    return render_template('forms/edit_venue.html', form=form, venue=venue)

  return redirect(url_for('show_venue', venue_id=venue_id))

#  Create Artist
#  ----------------------------------------------------------------

@app.route('/artists/create', methods=['GET'])
def create_artist_form():
  form = ArtistForm()
  return render_template('forms/new_artist.html', form=form)

@app.route('/artists/create', methods=['POST'])
def create_artist_submission():
  # called upon submitting the new artist listing form
  # TODO: insert form data as a new Venue record in the db, instead
  # TODO: modify data to be the data object returned from db insertion
  form = ArtistForm(request.form)
  data = None

  if not form.validate():
    flash('An error occurred. Artist ' + request.form.get('name', '') + ' could not be listed.')
    return render_template('forms/new_artist.html', form=form)

  try:
    data = Artist()
    populate_artist_from_form(data, form)
    db.session.add(data)
    db.session.commit()

  # on successful db insert, flash success
    flash('Artist ' + data.name + ' was successfully listed!')
  # TODO: on unsuccessful db insert, flash an error instead.
  # e.g., flash('An error occurred. Artist ' + data.name + ' could not be listed.')
  except Exception:
    db.session.rollback()
    flash('An error occurred. Artist ' + request.form.get('name', '') + ' could not be listed.')
  finally:
    db.session.close()

  return render_template('pages/home.html')


#  Shows
#  ----------------------------------------------------------------

@app.route('/shows')
def shows():
  # displays list of shows at /shows
  # TODO: replace with real venues data.
  show_rows = (
    db.session.query(Show)
    .join(Artist, Artist.id == Show.artist_id)
    .join(Venue, Venue.id == Show.venue_id)
    .options(contains_eager(Show.artist), contains_eager(Show.venue))
    .order_by(Show.start_time)
    .all()
  )
  data=[{
    "venue_id": show.venue_id,
    "venue_name": show.venue.name,
    "artist_id": show.artist_id,
    "artist_name": show.artist.name,
    "artist_image_link": show.artist.image_link,
    "start_time": show.start_time
  } for show in show_rows]
  return render_template('pages/shows.html', shows=data)

@app.route('/shows/create')
def create_shows():
  # renders form. do not touch.
  form = ShowForm()
  return render_template('forms/new_show.html', form=form)

@app.route('/shows/create', methods=['POST'])
def create_show_submission():
  # called to create new shows in the db, upon submitting new show listing form
  # TODO: insert form data as a new Show record in the db, instead
  form = ShowForm(request.form)

  if not form.validate():
    flash('An error occurred. Show could not be listed.')
    return render_template('forms/new_show.html', form=form)

  try:
    artist_id = int(form.artist_id.data)
    venue_id = int(form.venue_id.data)
    artist = db.session.get(Artist, artist_id)
    venue = db.session.get(Venue, venue_id)

    if artist is None or venue is None:
      raise ValueError('Artist or venue does not exist.')

    show = Show(
      artist_id=artist_id,
      venue_id=venue_id,
      start_time=form.start_time.data,
    )
    db.session.add(show)
    db.session.commit()

  # on successful db insert, flash success
    flash('Show was successfully listed!')
  # TODO: on unsuccessful db insert, flash an error instead.
  # e.g., flash('An error occurred. Show could not be listed.')
  # see: http://flask.pocoo.org/docs/1.0/patterns/flashing/
  except Exception:
    db.session.rollback()
    flash('An error occurred. Show could not be listed.')
  finally:
    db.session.close()

  return render_template('pages/home.html')

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
