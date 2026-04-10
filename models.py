from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case, func
from sqlalchemy.orm import contains_eager, joinedload


db = SQLAlchemy()


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


def current_time():
    return datetime.now()


def build_upcoming_show_count_expression():
    return func.sum(
        case(
            (Show.start_time > current_time(), 1),
            else_=0,
        )
    ).label('num_upcoming_shows')


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

    for show in sorted(shows, key=lambda current_show: current_show.start_time):
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

    for show in sorted(shows, key=lambda current_show: current_show.start_time):
        serialized_show = serialize_show_for_artist(show)
        if show.start_time > now:
            upcoming_shows.append(serialized_show)
        else:
            past_shows.append(serialized_show)

    return past_shows, upcoming_shows


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

    def apply_form(self, form):
        self.name = form.name.data
        self.city = form.city.data
        self.state = form.state.data
        self.address = form.address.data
        self.phone = form.phone.data
        self.genres = get_or_create_genres(form.genres.data)
        self.image_link = form.image_link.data
        self.facebook_link = form.facebook_link.data
        self.website = form.website_link.data
        self.seeking_talent = form.seeking_talent.data
        self.seeking_description = form.seeking_description.data

    def populate_form(self, form):
        form.name.data = self.name
        form.city.data = self.city
        form.state.data = self.state
        form.address.data = self.address
        form.phone.data = self.phone
        form.genres.data = genre_names(self)
        form.facebook_link.data = self.facebook_link
        form.image_link.data = self.image_link
        form.website_link.data = self.website
        form.seeking_talent.data = self.seeking_talent
        form.seeking_description.data = self.seeking_description

    @classmethod
    def fetch_grouped_for_listing(cls):
        upcoming_show_count = build_upcoming_show_count_expression()
        venue_rows = (
            db.session.query(
                cls.id,
                cls.name,
                cls.city,
                cls.state,
                upcoming_show_count,
            )
            .outerjoin(Show, Show.venue_id == cls.id)
            .group_by(cls.id)
            .order_by(cls.state, cls.city, cls.name)
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

        return list(grouped_venues.values())

    @classmethod
    def search_by_name(cls, search_term):
        upcoming_show_count = build_upcoming_show_count_expression()
        return (
            db.session.query(
                cls.id,
                cls.name,
                upcoming_show_count,
            )
            .outerjoin(Show, Show.venue_id == cls.id)
            .filter(cls.name.ilike(f'%{search_term}%'))
            .group_by(cls.id)
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def get_with_shows(cls, venue_id):
        venue = db.session.query(cls).options(joinedload(cls.genres)).filter(cls.id == venue_id).one_or_none()
        if venue is None:
            return None, []

        venue_shows = (
            db.session.query(Show)
            .join(Artist, Artist.id == Show.artist_id)
            .options(contains_eager(Show.artist))
            .filter(Show.venue_id == venue_id)
            .order_by(Show.start_time)
            .all()
        )
        return venue, venue_shows


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

    def apply_form(self, form):
        self.name = form.name.data
        self.city = form.city.data
        self.state = form.state.data
        self.phone = form.phone.data
        self.genres = get_or_create_genres(form.genres.data)
        self.image_link = form.image_link.data
        self.facebook_link = form.facebook_link.data
        self.website = form.website_link.data
        self.seeking_venue = form.seeking_venue.data
        self.seeking_description = form.seeking_description.data

    def populate_form(self, form):
        form.name.data = self.name
        form.city.data = self.city
        form.state.data = self.state
        form.phone.data = self.phone
        form.genres.data = genre_names(self)
        form.facebook_link.data = self.facebook_link
        form.image_link.data = self.image_link
        form.website_link.data = self.website
        form.seeking_venue.data = self.seeking_venue
        form.seeking_description.data = self.seeking_description

    @classmethod
    def fetch_listing(cls):
        return cls.query.order_by(cls.name).all()

    @classmethod
    def search_by_name(cls, search_term):
        upcoming_show_count = build_upcoming_show_count_expression()
        return (
            db.session.query(
                cls.id,
                cls.name,
                upcoming_show_count,
            )
            .outerjoin(Show, Show.artist_id == cls.id)
            .filter(cls.name.ilike(f'%{search_term}%'))
            .group_by(cls.id)
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def get_with_shows(cls, artist_id):
        artist = db.session.query(cls).options(joinedload(cls.genres)).filter(cls.id == artist_id).one_or_none()
        if artist is None:
            return None, []

        artist_shows = (
            db.session.query(Show)
            .join(Venue, Venue.id == Show.venue_id)
            .options(contains_eager(Show.venue))
            .filter(Show.artist_id == artist_id)
            .order_by(Show.start_time)
            .all()
        )
        return artist, artist_shows


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

    @classmethod
    def fetch_listing(cls):
        return (
            db.session.query(cls)
            .join(Artist, Artist.id == cls.artist_id)
            .join(Venue, Venue.id == cls.venue_id)
            .options(contains_eager(cls.artist), contains_eager(cls.venue))
            .order_by(cls.start_time)
            .all()
        )