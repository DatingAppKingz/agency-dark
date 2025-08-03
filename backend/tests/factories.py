"""Test factories for creating test data."""
from datetime import datetime
from typing import Optional, Dict, Any
import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker

from models.user import User, UserRole
from models.agency import Agency
from models.model import Model
from models.conversation import Conversation
from models.message import Message

fake = Faker()


class BaseFactory(SQLAlchemyModelFactory):
    """Base factory with common configuration."""
    
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = 'commit'


class AgencyFactory(BaseFactory):
    """Factory for creating Agency instances."""
    
    class Meta:
        model = Agency
    
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    subdomain = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-').replace(',', ''))
    description = factory.Faker('text', max_nb_chars=200)
    logo_url = factory.Faker('image_url')
    theme_settings = factory.LazyFunction(lambda: {
        'primary_color': fake.hex_color(),
        'secondary_color': fake.hex_color(),
        'font_family': fake.random_element(['Arial', 'Helvetica', 'Roboto'])
    })
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class UserFactory(BaseFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    id = factory.Faker('uuid4')
    email = factory.Faker('email')
    username = factory.Faker('user_name')
    full_name = factory.Faker('name')
    hashed_password = '$2b$12$test.hashed.password'  # Pre-hashed test password
    role = UserRole.MEMBER
    is_active = True
    is_verified = True
    agency_id = factory.SubFactory(AgencyFactory)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
    
    @factory.post_generation
    def permissions(self, create: bool, extracted: Optional[list], **kwargs):
        if not create:
            return
        
        if extracted:
            for permission in extracted:
                self.permissions.append(permission)


class ModelFactory(BaseFactory):
    """Factory for creating Model instances."""
    
    class Meta:
        model = Model
    
    id = factory.Faker('uuid4')
    user_id = factory.SubFactory(UserFactory, role=UserRole.MODEL)
    stage_name = factory.Faker('first_name')
    bio = factory.Faker('text', max_nb_chars=500)
    profile_image_url = factory.Faker('image_url')
    cover_image_url = factory.Faker('image_url')
    agency_id = factory.SubFactory(AgencyFactory)
    is_active = True
    commission_rate = factory.Faker('pydecimal', left_digits=2, right_digits=2, min_value=10, max_value=50)
    social_links = factory.LazyFunction(lambda: {
        'twitter': f"@{fake.user_name()}",
        'instagram': f"@{fake.user_name()}",
        'tiktok': f"@{fake.user_name()}"
    })
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class ConversationFactory(BaseFactory):
    """Factory for creating Conversation instances."""
    
    class Meta:
        model = Conversation
    
    id = factory.Faker('uuid4')
    model_id = factory.SubFactory(ModelFactory)
    chatter_id = factory.SubFactory(UserFactory, role=UserRole.CHATTER)
    platform = factory.Faker('random_element', elements=['onlyfans', 'fansly', 'chaturbate'])
    platform_conversation_id = factory.Faker('uuid4')
    fan_username = factory.Faker('user_name')
    fan_id = factory.Faker('uuid4')
    is_active = True
    last_message_at = factory.LazyFunction(datetime.utcnow)
    metadata = factory.LazyFunction(lambda: {
        'fan_location': fake.country(),
        'subscription_tier': fake.random_element(['basic', 'premium', 'vip']),
        'total_spent': float(fake.pydecimal(left_digits=4, right_digits=2, min_value=0, max_value=9999))
    })
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class MessageFactory(BaseFactory):
    """Factory for creating Message instances."""
    
    class Meta:
        model = Message
    
    id = factory.Faker('uuid4')
    conversation_id = factory.SubFactory(ConversationFactory)
    sender_type = factory.Faker('random_element', elements=['model', 'fan', 'chatter'])
    content = factory.Faker('text', max_nb_chars=200)
    media_urls = factory.LazyFunction(lambda: [fake.image_url()] if fake.boolean(chance_of_getting_true=30) else [])
    is_tip = False
    tip_amount = None
    is_read = False
    platform_message_id = factory.Faker('uuid4')
    created_at = factory.LazyFunction(datetime.utcnow)
    
    @factory.post_generation
    def set_sender_id(self, create: bool, extracted: Optional[str], **kwargs):
        if not create:
            return
        
        if self.sender_type == 'model':
            self.sender_id = self.conversation.model_id
        elif self.sender_type == 'chatter':
            self.sender_id = self.conversation.chatter_id
        else:  # fan
            self.sender_id = self.conversation.fan_id


def create_test_agency(**kwargs) -> Agency:
    """Create a test agency with defaults."""
    return AgencyFactory(**kwargs)


def create_test_user(agency: Optional[Agency] = None, **kwargs) -> User:
    """Create a test user with defaults."""
    if agency:
        kwargs['agency_id'] = agency.id
    return UserFactory(**kwargs)


def create_test_model(agency: Optional[Agency] = None, user: Optional[User] = None, **kwargs) -> Model:
    """Create a test model with defaults."""
    if agency:
        kwargs['agency_id'] = agency.id
    if user:
        kwargs['user_id'] = user.id
    return ModelFactory(**kwargs)


def create_complete_test_setup() -> Dict[str, Any]:
    """Create a complete test setup with agency, users, models, and conversations."""
    # Create agency
    agency = create_test_agency(name="Test Agency")
    
    # Create users
    admin = create_test_user(agency=agency, role=UserRole.AGENCY_ADMIN, email="admin@test.com")
    model_user = create_test_user(agency=agency, role=UserRole.MODEL, email="model@test.com")
    chatter = create_test_user(agency=agency, role=UserRole.CHATTER, email="chatter@test.com")
    
    # Create model profile
    model = create_test_model(agency=agency, user=model_user, stage_name="TestModel")
    
    # Create conversations
    conversation = ConversationFactory(
        model_id=model.id,
        chatter_id=chatter.id,
        platform="onlyfans"
    )
    
    # Create messages
    messages = [
        MessageFactory(conversation_id=conversation.id, sender_type='fan', content="Hi there!"),
        MessageFactory(conversation_id=conversation.id, sender_type='chatter', content="Hello! How are you?"),
        MessageFactory(conversation_id=conversation.id, sender_type='fan', content="I'm great, thanks!"),
    ]
    
    return {
        'agency': agency,
        'admin': admin,
        'model_user': model_user,
        'chatter': chatter,
        'model': model,
        'conversation': conversation,
        'messages': messages
    }