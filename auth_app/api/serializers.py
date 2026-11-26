from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    """Serializer for registering new users."""
    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'confirmed_password'
        ]
        extra_kwargs = {
            'password': {
                'write_only': True
            },
            'email': {
                'required': True
            }
        }

    def validate_email(self, value):
        """Ensure the email address is not already registered.

        The comparison is case-insensitive.

        Args:
            value (str): The email address submitted for registration.

        Returns:
            str: The unchanged email address if it is not yet in use.

        Raises:
            serializers.ValidationError: If a user with this email
                already exists.
        """
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'Email already exists'
            )
        return value

    def validate(self, attrs):
        """Check that the password and its confirmation match.

        Args:
            attrs (dict): The field values that passed field-level
                validation.

        Returns:
            dict: The unchanged attributes if both passwords match.

        Raises:
            serializers.ValidationError: If password and
                confirmed_password differ.
        """
        if attrs['password'] != attrs['confirmed_password']:
            raise serializers.ValidationError({
                'confirmed_password': 'Passwords do not match'
            })
        return attrs

    def create(self, validated_data):
        """Create a new user from the validated registration data.

        Removes confirmed_password and uses create_user so the password
        is stored hashed.

        Args:
            validated_data (dict): The validated registration data
                (username, email, password, confirmed_password).

        Returns:
            User: The newly created user instance.
        """
        validated_data.pop('confirmed_password')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )

        return user