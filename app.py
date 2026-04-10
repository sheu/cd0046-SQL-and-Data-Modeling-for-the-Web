#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

from datetime import datetime
import dateutil.parser
import babel
from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_migrate import Migrate
from flask_moment import Moment
import logging
from logging import Formatter, FileHandler
from forms import ArtistForm, ShowForm, VenueForm
from models import Artist, Show, Venue, db, genre_names, split_artist_shows, split_venue_shows
#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
db.init_app(app)

# TODO: connect to a local postgresql database
migrate = Migrate(app, db)

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
  data = Venue.fetch_grouped_for_listing()
  return render_template('pages/venues.html', areas=data);

@app.route('/venues/search', methods=['POST'])
def search_venues():
  # TODO: implement search on artists with partial string search. Ensure it is case-insensitive.
  # seach for Hop should return "The Musical Hop".
  # search for "Music" should return "The Musical Hop" and "Park Square Live Music & Coffee"
  search_term = request.form.get('search_term', '').strip()
  matching_venues = Venue.search_by_name(search_term)
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
  venue, venue_shows = Venue.get_with_shows(venue_id)
  if venue is None:
    abort(404)
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
    data.apply_form(form)
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
  data = db.get_or_404(Venue, int(venue_id))

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
  } for artist in Artist.fetch_listing()]
  return render_template('pages/artists.html', artists=data)

@app.route('/artists/search', methods=['POST'])
def search_artists():
  # TODO: implement search on artists with partial string search. Ensure it is case-insensitive.
  # seach for "A" should return "Guns N Petals", "Matt Quevado", and "The Wild Sax Band".
  # search for "band" should return "The Wild Sax Band".
  search_term = request.form.get('search_term', '').strip()
  matching_artists = Artist.search_by_name(search_term)
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
  artist, artist_shows = Artist.get_with_shows(artist_id)
  if artist is None:
    abort(404)
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
  artist = db.get_or_404(Artist, artist_id)
  # TODO: populate form with fields from artist with ID <artist_id>
  artist.populate_form(form)
  return render_template('forms/edit_artist.html', form=form, artist=artist)

@app.route('/artists/<int:artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
  # TODO: take values from the form submitted, and update existing
  # artist record with ID <artist_id> using the new attributes
  form = ArtistForm(request.form)
  artist = db.get_or_404(Artist, artist_id)

  if not form.validate():
    flash('An error occurred. Artist ' + artist.name + ' could not be updated.')
    return render_template('forms/edit_artist.html', form=form, artist=artist)

  try:
    artist.apply_form(form)
    db.session.commit()
  except Exception:
    db.session.rollback()
    flash('An error occurred. Artist ' + artist.name + ' could not be updated.')
    return render_template('forms/edit_artist.html', form=form, artist=artist)

  return redirect(url_for('show_artist', artist_id=artist_id))

@app.route('/venues/<int:venue_id>/edit', methods=['GET'])
def edit_venue(venue_id):
  form = VenueForm()
  venue = db.get_or_404(Venue, venue_id)
  # TODO: populate form with values from venue with ID <venue_id>
  venue.populate_form(form)
  return render_template('forms/edit_venue.html', form=form, venue=venue)

@app.route('/venues/<int:venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
  # TODO: take values from the form submitted, and update existing
  # venue record with ID <venue_id> using the new attributes
  form = VenueForm(request.form)
  venue = db.get_or_404(Venue, venue_id)

  if not form.validate():
    flash('An error occurred. Venue ' + venue.name + ' could not be updated.')
    return render_template('forms/edit_venue.html', form=form, venue=venue)

  try:
    venue.apply_form(form)
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
    data.apply_form(form)
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
  show_rows = Show.fetch_listing()
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
